import { MimirSurrealClient } from "../../../packages/db-surreal/src/client";

export interface SensedJobPosting {
  title: string;
  company: string;
  url: string;
  description: string;
  salaryMin?: number;
  salaryMax?: number;
  location?: string;
  skills: string[];
}

export const CANDIDATE_PROFILE = {
  targetRoles: [
    "Enterprise AI Solutions Engineering",
    "Solutions Architecture",
    "Agentic AI Architecture",
    "Platform Architecture",
    "Conversational AI Leadership",
    "Voice AI Enterprise Solutions",
  ],
  compFloorBase: 180000,
  compTargetTotal: 250000,
  coreSkills: ["voice ai", "conversational ai", "agentic", "architecture", "solutions", "llm", "enterprise"],
};

export function evaluateBantFit(job: SensedJobPosting): {
  budgetFit: boolean;
  needAlignment: number;
  authorityIdentified: boolean;
  timeline: string;
} {
  // 1. Budget Fit ($180k floor)
  const budgetFit = (job.salaryMax ?? 200000) >= CANDIDATE_PROFILE.compFloorBase;

  // 2. Need Alignment (Skills & Role matching)
  const descLower = (job.description + " " + job.title).toLowerCase();
  let matches = 0;
  for (const skill of CANDIDATE_PROFILE.coreSkills) {
    if (descLower.includes(skill)) matches++;
  }
  const needAlignment = Math.min(1.0, Math.round((matches / 4) * 100) / 100);

  return {
    budgetFit,
    needAlignment,
    authorityIdentified: false,
    timeline: "immediate",
  };
}

export async function ingestJobPostings(
  client: MimirSurrealClient,
  postings: SensedJobPosting[]
): Promise<number> {
  const db = client.getRawDb();
  let created = 0;

  for (const job of postings) {
    const slug = `${job.company}-${job.title}`.toLowerCase().replace(/[^a-z0-9]/g, "_");
    const leadId = `lead:${slug}`;
    const orgSlug = job.company.toLowerCase().replace(/[^a-z0-9]/g, "_");
    const orgId = `organization:${orgSlug}`;

    const bant = evaluateBantFit(job);

    // 1. Ensure Organization exists
    await db.query(
      `UPSERT ${orgId} SET name = $name, target_tier = 'tier_1', updated_at = time::now();`,
      { name: job.company }
    );

    // 2. Create Lead Node
    await db.query(
      `UPSERT ${leadId} SET 
        source_kind = 'job_posting',
        title = $title,
        external_url = $url,
        description = $description,
        salary_min = $salary_min,
        salary_max = $salary_max,
        state = 'discovered',
        bant = $bant,
        updated_at = time::now();`,
      {
        title: job.title,
        url: job.url,
        description: job.description,
        salary_min: job.salaryMin || null,
        salary_max: job.salaryMax || null,
        bant,
      }
    );
    created++;

    // 3. Topology: Organization CONTAINS Lead
    await client.createContainsEdge(orgId, leadId, "CONTAINS__SHARED");

    // 4. Issue KNOW Claim
    await client.issueKnowClaim({
      observer: "agent:job_sourcing_engine",
      method: "career_board_scraper",
      targetRef: leadId,
      weight: 1.0,
      evidenceDigest: `sha256:${Buffer.from(job.url).toString("hex").substring(0, 32)}`,
    });
  }

  return created;
}
