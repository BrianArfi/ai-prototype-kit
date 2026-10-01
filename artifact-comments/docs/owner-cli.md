# Owner CLI: reading and moderating comments

[Back to the README](../README.md)

`scripts/comments_cli.py`, Python 3.8 or later, standard library only. Readers cannot delete or edit anything; the owner does it here.

**On Cloudflare** (the default, `--backend cloudflare`):

```bash
# one page, through the public API, no credentials
python scripts/comments_cli.py list --base https://my-site.pages.dev --slug my-page

# every page, through the Cloudflare API
python scripts/comments_cli.py --namespace-title my-site-comments list

# remove a comment and its replies (the id is printed by list); they go to a trash
python scripts/comments_cli.py --namespace-title my-site-comments delete --slug my-page --id mg1k2x9fa3

# undo that delete
python scripts/comments_cli.py --namespace-title my-site-comments restore --slug my-page --id mg1k2x9fa3

# rebuild page summaries from the per-comment keys
python scripts/comments_cli.py --namespace-title my-site-comments repair
```

Credentials come from `--creds file.json` (`{"api_token", "account_id", "kv_namespace_id"}`) or from `CF_API_TOKEN`, `CF_ACCOUNT_ID` and `CF_KV_NAMESPACE_ID`.

**On the self-hosted Node server**, add `--backend node` with the server URL and its owner token (`--token`, or `ARTIFACT_COMMENTS_TOKEN`). `list`, `delete` and `restore` then go through the owner endpoints:

```bash
python scripts/comments_cli.py --backend node --base http://127.0.0.1:8787 --token "$ARTIFACT_COMMENTS_TOKEN" list
python scripts/comments_cli.py --backend node --base http://127.0.0.1:8787 --token "$ARTIFACT_COMMENTS_TOKEN" delete --slug my-page --id mg1k2x9fa3
python scripts/comments_cli.py --backend node --base http://127.0.0.1:8787 --token "$ARTIFACT_COMMENTS_TOKEN" restore --slug my-page --id mg1k2x9fa3
```

`repair` and `setup` manage Workers KV, so they are Cloudflare only and refuse on `--backend node`. Flags that belong to the other backend (`--creds` on node, `--token` on Cloudflare) are refused rather than ignored.

