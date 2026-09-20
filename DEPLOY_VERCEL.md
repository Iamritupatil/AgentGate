# Deploy the AgentGate control room on Vercel

The control room is a static Vite bundle. Vercel builds and serves it; the Cedar
gate stays on EC2 (see [DEPLOY_EC2.md](DEPLOY_EC2.md)). Deploy the backend first
— the frontend is pointed at it by address.

```
  browser ──https──▶ Vercel edge
                       ├── /            React bundle
                       └── /api/*       rewrite, server-side
                                          │
                                          ▼
                              EC2: nginx ──▶ uvicorn 127.0.0.1:8000
                                               Cedar decides
```

## Why the API goes through Vercel

The browser loads the page over HTTPS. If it then called `http://<ec2-ip>/api`
directly, the browser would block every request as mixed content, and an HTTPS
backend would need a domain and a certificate before the demo could run at all.

The rewrite in [frontend/vercel.json](frontend/vercel.json) removes both
problems. `/api/*` is proxied by Vercel's edge, server-side, so the browser only
ever sees its own origin: no mixed content, and no CORS headers involved. It is
also why `VITE_API_BASE_URL` stays at its default `/api` — no EC2 address is
compiled into the public bundle.

## 1. Point the frontend at your backend

From the repository root:

```bash
cd frontend
npm run set:backend -- http://<EC2_PUBLIC_IP>
```

That rewrites the `/api/:path*` destination in `vercel.json`. Use the HTTPS
domain instead once [deployment/enable-tls.sh](deployment/enable-tls.sh) has
run. Commit the change: Vercel reads this file from the deployed source.

Use an Elastic IP. A stopped instance comes back with a different public
address, and the rewrite would then point at nothing.

## 2. Deploy

```bash
npm install -g vercel   # already installed in this workspace
cd frontend
vercel login
vercel --prod
```

The first run asks which scope and project to use and writes
`frontend/.vercel/`, which is git-ignored. `vercel --prod` after that.

To deploy from Git instead, import the repository in the Vercel dashboard and
set **Root Directory** to `frontend`. Everything else — framework, build
command, output directory, Node version — is already declared in `vercel.json`
and `package.json`.

No environment variables need to be set in the Vercel dashboard. The bundle
carries no credential and no backend address.

## 3. Verify

```bash
bash deployment/smoke-test.sh https://<your-project>.vercel.app
```

This exercises the gate through the public URL: health, an autonomous refund, a
refund that needs a human, a refused refund, and the five-case policy bench. It
is the check that proves the rewrite works, not just that the page loads.

Then open the URL and walk the demo:

1. Control Room: Scenario A, Run.
2. Reset, Scenario B, Run, Approve, verify the exact refund.
3. Reset, Scenario C, Run, verify both DENY rows.
4. Policy Test Bench, run 5 checks.
5. Playground, run the presets.
6. Policy Studio, generate a draft, inspect the Cedar, Activate.
7. Integrate, copy the runtime-base examples.

## Option B: call the backend directly

Skip the proxy only if you want the browser to talk to EC2 itself — a separate
`api.` hostname, or one fewer hop. It costs more setup, not less:

1. Run `sudo bash deployment/enable-tls.sh api.example.com you@example.com` on
   the instance. Without a certificate the browser blocks the calls.
2. In the Vercel dashboard set `VITE_API_BASE_URL=https://api.example.com/api`
   for the Production environment, and redeploy so the value is compiled in.
3. In `/etc/agentgate/agentgate.env` on the instance, allow your Vercel origin:

   ```ini
   AGENTGATE_CORS_ORIGINS='["https://your-project.vercel.app"]'
   AGENTGATE_CORS_ORIGIN_REGEX=https://your-project-[a-z0-9]+-[a-z0-9-]+\.vercel\.app
   ```

   The single quotes matter: systemd strips bare double quotes and the JSON
   would no longer parse. The regex covers preview deployments, which get a new
   hostname every time and so cannot be listed in advance. Restart with
   `sudo systemctl restart agentgate`.

The rewrite in `vercel.json` becomes unused, but leaving it in place is
harmless — `VITE_API_BASE_URL` makes the frontend use absolute URLs.

## Troubleshooting

**Every `/api` call returns 404 and `curl http://<ec2-ip>/api/health` works.**
The rewrite destination is stale. Re-run `npm run set:backend` and redeploy;
`vercel.json` is read from the deployment, not from your working copy.

**`/api` calls fail only after TLS was enabled.** Certbot adds an HTTP-to-HTTPS
redirect, and the proxy does not follow a redirect on a POST. Point the rewrite
at the `https://` URL.

**The URL asks you to log in to Vercel.** That is Deployment Protection on
preview URLs, not an app error. Use the production URL or turn it off under
Project Settings → Deployment Protection.

**The build fails on the Node version.** `package.json` pins `"node": "24.x"`,
which Vercel honours. An open-ended range like `>=24` is what it rejects.
