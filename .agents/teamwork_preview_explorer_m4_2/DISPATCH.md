## 2026-08-24T09:10:52Z
You are Explorer M4.2 for Milestone M4 (TypeScript SDK Extension).

Read:
- ORIGINAL_REQUEST: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/ORIGINAL_REQUEST.md
- PROJECT.md: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/PROJECT.md
- Working Directory: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_2
- Workspace: /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

OBJECTIVE:
Investigate and produce an exact, production-ready specification and technical design for extending the `@ultradex/sdk` TypeScript package (`sdk/typescript/`).

TASKS:
1. Inspect `sdk/typescript/package.json`, `sdk/typescript/src/`, `sdk/typescript/tests/`, and existing client/query patterns.
2. Design TypeScript types, Zod schemas, GraphQL query documents, and client SDK methods for:
   - Candidate Profile
   - Leads (`getLeads`, `getLead`, `createLead`, `convertLead`)
   - Organizations (`getOrganizations`, `getOrganization`, `createOrganization`, `updateOrganization`)
   - Contacts (`getContacts`, `getContact`)
   - Next Best Actions (`getNextBestActions`)
   - Recruiter 3-Pill Replies (`generateRecruiterReplies`)
   - Calendar Availability & Events (`getAvailability`, `getCalendarEvents`)
   - Omnichannel Messaging (`sendMessage`, `createDraft`, `getMessages`)
   - Interview Debriefs (`getInterviewDebriefs`, `getInterviewDebrief`)
3. Design Vitest test suite structure for `sdk/typescript/tests/`.
4. Write your full design report to:
   /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_2/handoff.md
5. Send a message to parent upon completion.
