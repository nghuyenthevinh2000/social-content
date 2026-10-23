# File & Skill Selector Interactive Demo

An interactive visual demonstration of how Antigravity uses TypeSafe Jev System One to route incoming requests before model execution:

1. **PreInvocation Lifecycle Hook** receives the user's prompt.
2. **Jev Skill Router** identifies the primary skill and required sub-resources.
3. **Jev File Selector** resolves the target directory and lead file via hierarchical drilldown.
4. An **ephemeral directive** is injected into the model context with zero repository wandering.
