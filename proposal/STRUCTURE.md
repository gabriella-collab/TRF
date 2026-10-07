# TRF site proposal

This proposal reflects the attached blank Fall 2026 template. It does not invent completed answers or identify the people in the cover image. The homepage uses a placeholder for a group photo chosen by the owner.

## Navigation

- Fall 2026 homepage
- TRF Updates: group updates, upcoming dates, prayer requests / celebrations, notes
- The crew: individual pages for Abby, Angel, Christine, Debbie, Gabby, Gloria, Hannah, Heidi, Rhea, Stephanie, Sue
- Gratitude: each member's seasonal gratitude answer
- Halloween Archives: childhood photo and favorite costume answer by member
- Past editions: seasonal snapshots retained by edition

## Fillable member page

All prompts use optional short text answers, with clear save status and mobile-friendly controls.

Life lately: Current season in 3 words; Biggest life update since summer; Something really good right now; Something that's been hard; How are you really doing?

Family + life: Quick family / kid update; A recent win or fail that made you laugh; Work / life update.

Fall check-in: What are you thankful for right now?; What was your favorite Halloween costume as a kid?; What are you looking forward to this holiday season?

Current favorites: Watching; Listening to; Eating / drinking; Loving / recommending; Text me about.

Photos: 3–5 recent photos, plus one optional childhood Halloween photo. Allow partial drafts, captions, replacement, and removal. Validate type, size, and count on the server. Strip location metadata and safely decode image uploads.

## Proposed data structure

| Record | Main fields |
| --- | --- |
| Member | id, display_name, display_order |
| Edition | id, title, season, year, status (open / archived) |
| Seasonal response | member_id, edition_id, prompt answers, updated_at; unique per member + edition |
| Photo | id, response_id, kind (recent / childhood), private storage key, caption, display_order |
| Group updates | edition_id, group_updates, upcoming_dates, prayer_requests_celebrations, notes, updated_at |

Gratitude and Halloween pages read the same response records so answers stay consistent. Archived editions are read-only by default.

## Password protection and persistence

Use a server-side shared-password login with a password hash, rate limits, and secure HttpOnly sessions. Protect all pages, response APIs, and photo endpoints; do not put the password or private data in public JavaScript. Use a persistent database and private photo storage with server-authorized access. Use HTTPS when deployed. Configure the actual password securely at deployment, never in chat or committed files.

A shared password allows every signed-in friend to view and edit all member entries. Choosing a name is not identity verification. If edits must be restricted to each person, use individual accounts instead.

## Current proposal boundary

index.html is a responsive, self-contained homepage design preview with navigation concept dialogs. It has no authentication, upload handling, database, or functioning editor. No private responses or photos have been published. The full build follows design review as requested.
