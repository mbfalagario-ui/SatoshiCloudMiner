==========================================================================
 SATOSHI CLOUD MINER · SHIP-A-CLONE BUNDLE · v1.0
==========================================================================

WHAT IS IN THIS ZIP
-------------------
1. Foolproof_iOS_Clone_Prompts_Playbook.pdf
     The full 17-page playbook (master prompt + 10 numbered prompts +
     LTC+DOGE variant + gotchas + reality-checks).

2. PRODUCT_SPEC_Satoshi_Cloud_Miner.md
     The canonical product spec for re-building Satoshi Cloud Miner
     (BTC). Attach this when you send PROMPT 01 from the playbook.

3. PRODUCT_SPEC_LTC_DOGE_Cloud_Miner.md
     The canonical product spec for the Litecoin + Dogecoin variant.
     Attach this when you send PROMPT L01 from the playbook.

HOW TO USE (3 STEPS)
--------------------
A. To re-clone Satoshi Cloud Miner from scratch in a fresh chat:
     1. Open the playbook PDF, copy the "Master Prompt" (page 3).
     2. Replace every <PLACEHOLDER> with your real value.
     3. Attach PRODUCT_SPEC_Satoshi_Cloud_Miner.md and send.
     4. Then send PROMPTS 01 through 10 in order (one per message).

B. To build the Litecoin + Dogecoin variant in a fresh chat:
     1. Open the playbook PDF, jump to Section 6 (page 11+).
     2. Copy the "Master Prompt — LITECOIN + DOGECOIN" (page 15).
     3. Replace every <PLACEHOLDER>.
     4. Attach PRODUCT_SPEC_LTC_DOGE_Cloud_Miner.md and send.
     5. Then send PROMPTS L01 through L10 in order.

CREDENTIALS YOU WILL NEED TO PASTE (collect ONCE, reuse forever)
-----------------------------------------------------------------
- Apple Team ID
- App Store Connect App Manager API key (.p8 + Key ID + Issuer ID)
- App Store Connect IAP Server API key (.p8 + Key ID)
- Expo personal access token
- ASC app record (bundle ID + app ID) for the new app
- Emergent universal LLM key  (or your OpenAI/Anthropic/Gemini key)
- For SCM: Blink Wallet API key + Blink USD Wallet ID
- For LTC+DOGE: NowPayments API key + IPN secret + LTC/DOGE addresses

WHAT THE AGENT WILL DO ON ITS OWN
----------------------------------
- Enumerate App Store Connect IAPs via API (no SKUs invented in code)
- Build backend skeleton + Expo Router skeleton
- Wire all integrations with a /api/diag/* endpoint per vendor
- Build UI from the attached spec
- Generate marketing assets with pixel-level verification
- Run quality gates (expo-doctor + tsc + backend regression)
- EAS build + EAS submit + ASC metadata upload (one-shot)
- Arm an auto_ship watcher so v1.0.1 ships automatically after approval

YOU DO NOT HAVE TO
-------------------
- Read any code
- Touch App Store Connect manually
- Write any markdown yourself
- Decide on file names or directory layout
- Re-explain anything between prompts

==========================================================================
Generated 2026-05-27. Compatible with the Emergent Expo + FastAPI template.
==========================================================================
