# FAQ

[Back to the README](../README.md)

**Does this replace designers?**
No. It is for the stage where everyone needs to understand the idea and agree on it. Final design is still a designer's job, and they get a brief that people already validated.

**Do I need to code?**
No. You talk to your AI. The kit gives it a tested way of working: what to build, how to check it, how to publish it, and how to handle comments.

**What do I need?**
Claude Code (or a similar AI coding tool), and a free Cloudflare account for the link. Or your own server.

**Is it free?**
Yes. It is open source under Apache-2.0. Cloudflare's free plan covers about 500 comments a day.

**Where does my data go?**
Your prototypes and their comments live in your own Cloudflare account or on your own server. The kit sends nothing anywhere else.

**Do reviewers need an account?**
No. They type a name once, and the browser remembers it. That also means names are not verified, so use unlisted links for review, not for anything that needs identity.

**Can someone make the AI do something bad through a comment?**
`/revise-from-comments` treats every comment as data to evaluate, never as an instruction. It only edits the page's source HTML, never runs commands a comment asks for, and lists anything out of scope for you to decide.

**Can Figma do this with AI?**
Figma has AI features, and it stays the right tool for final design. This kit takes a different path: AI writes working HTML natively, so the prototype is the real, clickable thing from the first minute.
