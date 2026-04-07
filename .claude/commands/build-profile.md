Build or update an investor profile for a user by conducting a structured interview.

## Steps

1. **Ask for user ID** — confirm who we are building the profile for.

2. **Present investment frameworks** — call `list_investment_frameworks` and present the options clearly:
   - Show framework name (formatted), description, and notable investors as examples.
   - Ask the user to pick the one that best matches their philosophy.
   - If they are unsure, ask: *"Do you focus more on finding undervalued companies, high-growth disruptors, macroeconomic trends, or steady income?"* and guide them to the closest match.

3. **Collect followed stocks** — ask which stock tickers they follow or hold.
   - Prompt: *"Which stocks or tickers are you most focused on? List as many as you like."*

4. **Collect followed themes** — ask which broad themes matter to them.
   - Present the available themes: technology, healthcare, financials, energy, consumer_discretionary, consumer_staples, industrials, materials, real_estate, utilities, communication_services, crypto.
   - Prompt: *"Which of these sectors or themes are relevant to your portfolio?"*

5. **Conduct the interest interview** — for each stock and theme, ask 2–3 targeted questions based on the selected framework:

   - **Value**: *"What is your thesis on [holding]'s competitive moat? What would make you reconsider this position?"*
   - **GARP**: *"What earnings growth are you expecting from [holding]? Do you think it's fairly priced for that growth?"*
   - **Disruptive Growth**: *"What disruption does [holding] represent? What's the TAM you're thinking about?"*
   - **Macro**: *"How does [holding] fit into your macro thesis? What policy or cycle signal matters most for it?"*
   - **Momentum**: *"What trend or catalyst are you riding with [holding]? What would signal the trend is reversing?"*
   - **Income**: *"What yield or payout does [holding] offer? How sensitive is it to interest rate moves?"*

   Collect the answers naturally — do not make it feel like a form. 2–3 exchanges per holding is enough.

6. **Synthesize reasons** — once the interview is complete, call `generate_profile_interest_reasons` with:
   - The selected framework id
   - The stock tickers and theme ids
   - A single `user_context` string summarising everything the user said (concatenate key points from the interview)

7. **Review with user** — show the generated `interest_reasons` to the user.
   - Ask: *"Does this capture your thinking accurately? Would you like to adjust anything?"*
   - If they request changes, update `user_context` with their corrections and call `generate_profile_interest_reasons` again.

8. **Save the profile** — call `save_user_profile` with the confirmed data.
   - Confirm: *"Your profile has been saved. Alerts will be evaluated against your [framework] framework and your stated reasoning for each holding."*
