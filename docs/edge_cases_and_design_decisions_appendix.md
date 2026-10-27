# Appendix: Edge Cases and Product Owner Decisions

**Purpose:** During the design and architecture review, several edge cases, potential exploits, and edge-case collisions were identified. Because this is a low-intensity, non-commercial hobby project intended for friends and family, the Product Owner has explicitly decided to favor simplicity over complex, over-engineered protections. 

The Master Agent and Dev Agent must adhere to these decisions and **avoid building unnecessary anti-cheat mechanisms or complex conflict resolutions.**

## 1. Intersecting Reveals (Free Letters)
* **The Identified Risk:** If a player uses the "Personal Reveal" feature on a long Across clue, they gain the intersecting letters for multiple Down clues. They lose eligibility for the Across clue, but could theoretically use the revealed letters to easily solve the Down clues for points.
* **Product Owner Decision:** **Approved / No Action Required.** 
* **Implementation Directive:** Do not build complex logic to penalize players for using intersecting letters. The game relies on good faith. A player only loses point eligibility for the specific clue they clicked "Reveal" on.

## 2. Multiple Pending Submissions
* **The Identified Risk:** If an official answer is missing (Pending state), and a player submits multiple different guesses before the admin updates the answer, there could be a conflict over which submission to evaluate.
* **Product Owner Decision:** **Approved / Unlimited Retries.**
* **Implementation Directive:** There is no limit on the number of attempts a player can make. The system should simply evaluate submissions as they come in or process the most recent/relevant pending submission once the admin provides the answer. Keep the logic straightforward.

## 3. Brute-Force Guessing / Spamming
* **The Identified Risk:** Players receive 0 points for a wrong answer but can retry instantly. A player could spam random letter combinations on a short word until they guess it correctly, bypassing the mental challenge.
* **Product Owner Decision:** **Ignored / Trust the Players.**
* **Implementation Directive:** This is a hobby game, not a commercial product. Do NOT implement rate-limiting, timeouts, penalty point deductions, or CAPTCHAs. Assume players act in good faith.

## 4. Revoking Public Ownership (Admin Typo Corrections)
* **The Identified Risk:** If an admin typos an official answer (e.g., "APPEL"), and a player submits that typo, they get 2 points and the public ownership color. If the admin later corrects the answer to "APPLE", the system would normally need complex UI logic to strip the color from the first player and award it to someone else.
* **Product Owner Decision:** **First is First / Keep the Color.**
* **Implementation Directive:** The first person to successfully match the active official answer gets the 2 points and their color permanently locks on the public board. If an admin later corrects a typo, retroactive points (+1) can be awarded to others based on the audit log, but do NOT build UI logic to revoke or change the public ownership color on the board.

## 5. Exact Timestamp Collisions (Tie-Breakers)
* **The Identified Risk:** If two players submit the exact same correct answer at the exact same millisecond, the system needs a deterministic tie-breaker to decide who gets 2 points and who gets 1 point.
* **Product Owner Decision:** **Out of Scope / Low Probability.**
* **Implementation Directive:** Because this is a low-traffic, low-intensity application where rooms live for a few hours or days, the mathematical probability of a true millisecond collision is negligible. Do not over-engineer a complex tie-breaker mechanism. Simply rely on the natural chronological processing order of the backend/database.