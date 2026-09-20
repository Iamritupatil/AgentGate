# Deploy the AgentGate API on EC2

This instance serves the Cedar gate and nothing else. The control room is built
and served by Vercel ([DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)). Deploy this half
first: the frontend is pointed at this box by address.

Approvals and the timeline live in process memory, so this runs as exactly one
Uvicorn worker. A second worker would answer with a different pending queue than
the one that issued the approval.

## 1. Instance and security group

Ubuntu 24.04, `t3.small` or larger. Allow:

- TCP 22 from your IP only
- TCP 80 from `0.0.0.0/0`
- TCP 443 from `0.0.0.0/0` (only if you will enable TLS)
- Never TCP 8000 — Uvicorn binds to loopback and is reached only through nginx

Attach an Elastic IP. A stopped instance returns with a different public
address, and the Vercel rewrite would then point at nothing.

## 2. Get the repository onto the instance

```bash
ssh ubuntu@<EC2_PUBLIC_IP>
sudo apt update && sudo apt install -y git
git clone <your-repo-url> ~/agentgate
```

No remote yet? Copy the working tree up instead, from your machine:

```bash
rsync -a --exclude node_modules --exclude .venv --exclude .git \
  ./ ubuntu@<EC2_PUBLIC_IP>:~/agentgate/
```

## 3. Bootstrap

```bash
cd ~/agentgate
sudo bash deployment/bootstrap-ec2.sh
```

One command, and it is safe to re-run. It installs Python, nginx and the build
tools; creates the `agentgate` system user; writes
`/etc/agentgate/agentgate.env` from the example if absent; installs the systemd
unit and the API vhost; disables nginx's default site; then builds the
virtualenv and starts the service.

Node is deliberately not installed. Vercel builds the frontend.

Check it:

```bash
curl -fsS http://127.0.0.1:8000/health     # the service
curl -fsS http://<EC2_PUBLIC_IP>/health    # through nginx, from your machine
```

## 4. Configure

Settings live in `/etc/agentgate/agentgate.env`, kept `0640 root:agentgate`
because it can hold an AI key. See
[deployment/agentgate.env.example](deployment/agentgate.env.example).

Leave `AGENTGATE_CORS_ORIGINS=[]` for the default topology. The browser talks to
Vercel, Vercel reaches this box server-side, and no CORS header is involved. You
only need origins here if the browser calls this host directly — Option B in the
Vercel guide.

Any JSON value must be wrapped in single quotes. systemd parses this file like a
shell and strips bare double quotes, which would leave pydantic with malformed
JSON and the service refusing to start.

```bash
sudo nano /etc/agentgate/agentgate.env
sudo systemctl restart agentgate
```

## 5. TLS (recommended before sharing the link)

With the proxy topology the browser's connection to Vercel is already HTTPS;
what is unencrypted is the edge-to-EC2 hop. Close it once a domain points here:

```bash
sudo bash deployment/enable-tls.sh api.example.com you@example.com
```

It installs certbot, claims the domain in the vhost, requests the certificate
and enables an HTTP-to-HTTPS redirect. Renewal runs from certbot's systemd
timer.

Afterwards re-point the frontend, because the proxy does not follow a redirect
on a POST:

```bash
cd frontend && npm run set:backend -- https://api.example.com && vercel --prod
```

## 6. Redeploy after a code change

```bash
cd ~/agentgate && git pull
sudo bash deployment/deploy-backend.sh
```

It syncs the source to `/opt/agentgate`, reinstalls pinned dependencies,
restarts the unit and fails loudly with the last 40 log lines if the service
does not answer within 30 seconds. `backend/data/` — the Policy Studio store —
is preserved across deploys.

Dependencies install from `backend/requirements.txt`, exported from `uv.lock`
with hashes, so pip refuses any artifact that differs from the lock the app was
tested against. After changing dependencies, regenerate it:

```bash
cd backend && uv export --frozen --no-dev --no-emit-project \
  --format requirements-txt -o requirements.txt
```

## 7. Verify the whole path

Once Vercel is deployed, test through the URL the browser actually uses:

```bash
bash deployment/smoke-test.sh https://<your-project>.vercel.app
```

Against this instance alone:

```bash
bash deployment/smoke-test.sh http://<EC2_PUBLIC_IP>
```

FastAPI's interactive docs are at `http://<EC2_PUBLIC_IP>/docs`. Postman should
target that same base URL, never port 8000.

## Operations

```bash
sudo journalctl -u agentgate -f          # follow the log
sudo systemctl restart agentgate         # after an env change
sudo systemctl status agentgate          # is it running
sudo nginx -t && sudo systemctl reload nginx
```

The service is hardened in [deployment/agentgate.service](deployment/agentgate.service):
no new privileges, a read-only filesystem apart from `backend/data`, no access
to home directories. If you add a path the app must write, it needs a matching
`ReadWritePaths=` line or the write fails with a permission error that looks
like a bug in the app.

## Single-box alternative

[deployment/nginx-agentgate.conf](deployment/nginx-agentgate.conf) is the
older all-in-one vhost: it serves `frontend/dist` from this instance as well as
the API, with no Vercel involved. It needs Node on the box and a `npm run build`
in `frontend/`. Use it only if you want one host to own everything.

The deployment is not finished until `deployment/smoke-test.sh` passes against
the public URL and the browser scenarios run against it.
