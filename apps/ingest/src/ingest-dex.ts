import { MimirSurrealClient } from "../../../packages/db-surreal/src/client";

export interface DexRawContact {
  id: string;
  name?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  job_title?: string;
  company?: string;
  linkedin_url?: string;
}

export async function syncDexContacts(
  client: MimirSurrealClient,
  dexApiKey: string,
  limit = 100
): Promise<{ organizationsCreated: number; contactsCreated: number }> {
  const db = client.getRawDb();
  
  // Fetch from Dex API
  const response = await fetch(`https://api.getdex.com/api/v1/contacts?limit=${limit}`, {
    headers: {
      Authorization: `Bearer ${dexApiKey}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Dex API error: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  const contacts: DexRawContact[] = data.contacts || data.data || [];

  let orgsCreated = 0;
  let contactsCreated = 0;

  for (const c of contacts) {
    const contactId = `contact:${c.id}`;
    const companyName = (c.company || "").trim();

    // 1. Upsert Organization if present
    let orgId: string | null = null;
    if (companyName && companyName.length > 1) {
      const orgSlug = companyName.toLowerCase().replace(/[^a-z0-9]/g, "_");
      orgId = `organization:${orgSlug}`;

      await db.query(
        `UPSERT ${orgId} SET 
          name = $name,
          advocacy_rating = 0.5,
          updated_at = time::now();`,
        { name: companyName }
      );
      orgsCreated++;
    }

    // 2. Classify role (Recruiter, Champion, Executive, Peer)
    const title = (c.job_title || "").toLowerCase();
    let contactRole = "peer";
    if (title.includes("recruiter") || title.includes("talent") || title.includes("ta ")) {
      contactRole = "recruiter";
    } else if (title.includes("vp") || title.includes("chief") || title.includes("head of") || title.includes("director")) {
      contactRole = "champion";
    }

    // 3. Upsert Contact node (Preserving the person's identity and headline)
    await db.query(
      `UPSERT ${contactId} SET 
        name = $name,
        email = $email,
        linkedin_url = $linkedin_url,
        headline = $headline,
        contact_role = $contact_role,
        relationship_strength = 0.8,
        updated_at = time::now();`,
      {
        name: c.name || `${c.first_name || ""} ${c.last_name || ""}`.trim() || "Unknown",
        email: c.email || null,
        linkedin_url: c.linkedin_url || null,
        headline: c.job_title || null,
        contact_role: contactRole,
      }
    );
    contactsCreated++;

    // 4. Create HAVE Topology Edges: Organization CONTAINS Contact & Contact CONNECTS_TO Nate
    if (orgId) {
      await client.createContainsEdge(orgId, contactId, "CONTAINS__SHARED");
    }
    await client.createConnectsToEdge(contactId, "contact:nate", "CONNECTS_TO__SHARED");

    // 5. Issue KNOW Claim Receipt for the contact
    await client.issueKnowClaim({
      observer: "agent:sense_dex_worker",
      method: "dex_v1_sync",
      targetRef: contactId,
      weight: 0.95,
      evidenceDigest: `sha256:${Buffer.from(JSON.stringify(c)).toString("hex").substring(0, 32)}`,
    });
  }

  return { organizationsCreated: orgsCreated, contactsCreated: contactsCreated };
}

if (import.meta.main) {
  const dexApiKey = process.env.DEX_API_KEY;
  if (!dexApiKey) {
    console.error("DEX_API_KEY environment variable is required.");
    process.exit(1);
  }
  const client = new MimirSurrealClient();
  await client.connect();
  console.log("Connected to SurrealDB. Starting Dex Ingestion...");
  const res = await syncDexContacts(client, dexApiKey, 100);
  console.log(`✓ Synced ${res.contactsCreated} contacts and ${res.organizationsCreated} organizations.`);
  await client.close();
}
