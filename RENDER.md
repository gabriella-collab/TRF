# Get TRF live on Render

1. In Render, select New → Blueprint.
2. Connect gabriella-collab/TRF and select main.
3. Render reads render.yaml. Review its paid Starter service and 1 GB persistent disk pricing before creating it.
4. When prompted for TRF_PASSWORD, enter a strong group password directly in Render. Do not send it in chat.
5. Deploy. Open the HTTPS address Render provides and sign in.
6. Save a test answer, upload a photo, and verify both are still there after a service restart before inviting friends.

The disk retains the database, images, and session signing key. Back it up securely. Everyone with the shared password can view and edit all pages. Changing TRF_PASSWORD requires redeployment and does not revoke existing sessions; see README.md to revoke sessions. There are no earlier editions yet.

The Blueprint uses a paid service because this app requires a persistent disk. Render displays the current price before you confirm. Do not use ephemeral storage for real responses.
