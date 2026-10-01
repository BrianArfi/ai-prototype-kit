# The publish script

[Back to the README](../README.md)

`scripts/publish.py` reads `kit.json` in your project root:

```json
{
  "project": "my-prototypes",
  "title": "Prototypes",
  "comments": true,
  "pages": [
    { "name": "Coffee order", "source": "prototypes/coffee-order.html" }
  ]
}
```

| Command | Does |
| :--- | :--- |
| `init --project NAME` | Writes `kit.json`. The project name becomes the subdomain |
| `add "Name" file.html` | Adds a page, or replaces the page with the same name and keeps its link |
| `build` | Builds `.kit-build/_site/`: one clean URL per page, the comment script added, an index page. Uploads nothing |
| `deploy --dry-run` | Builds and prints the links it would publish |
| `deploy` | Builds and uploads to Cloudflare Pages. The first run creates the project and the comment store |
| `serve` | Runs the built site on your machine, with comments |
| `list`, `comments [slug]` | Shows the links, or reads the comments |

Rather host it yourself? The comment server is one Node file with SQLite, and it can serve the pages too. See [Choose your backend](../artifact-comments/README.md#choose-your-backend).
