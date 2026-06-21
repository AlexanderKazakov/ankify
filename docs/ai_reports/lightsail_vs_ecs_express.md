# Hosting Options Explained: Lightsail vs ECS Express

**Who this is for:** someone who is new to AWS hosting and wants plain-language
explanations, not jargon. It covers only the two families you asked about —
**Lightsail** and **ECS Express** — plus the side topics you raised: domain names,
why the load balancer is expensive, running several apps at once, and using a
"remote PC" to run a coding agent.

**App Runner is not covered here** because you said to skip it. The current Lambda
setup is covered in other docs (`docs/deployment_spec.md`).

**Prices and facts checked:** 2026-06-16, region `eu-central-1` (Frankfurt). Cloud
prices change over time. Re-check the linked pricing pages before you commit money.

---

## Quick answers to your questions

If you only read one section, read this. Each line points to the full explanation below.

1. **Lightsail or ECS — which is simpler?** Lightsail. Fewer new ideas to learn, and
   the domain and HTTPS setup is mostly done for you. See [§7](#7-how-much-easier-is-lightsail).
2. **Can I run several websites and MCP servers at once?** Yes, in both. They work very
   differently. ECS Express makes many services share one load balancer. A Lightsail
   *instance* (a rented computer) can host many sites itself. See [§5](#5-running-several-apps-at-once).
3. **Can I have a remote PC to run Claude Code on?** Yes — but not with the *container*
   options. You need a Lightsail **instance** (a virtual computer you log into) or EC2.
   See [§6](#6-a-remote-pc-for-claude-code-and-dev-work).
4. **Domain names — how do they work, and Route 53 vs Cloudflare?** See [§8](#8-domain-names-and-route-53-vs-cloudflare).
   Short version: keep Cloudflare (it is free and fine); move to Route 53 only if you
   want everything in one place.
5. **Why is the ALB so expensive?** Because it bills by the hour, all the time, even with
   zero traffic, and the minimum is about $20/month. See [§4](#4-why-is-the-alb-so-expensive).

**My recommendation, in one line:** if you want to run several small things and also
have a box to run Claude Code on, a **Lightsail instance (a rented Linux computer)** is
the best single answer. If you want AWS to manage the containers for you and you may run
several services, **ECS Express** fits. Full reasoning in [§9](#9-recommendation).

---

## 1. First, the words you need

You do not need to memorize these. Come back when a word is unclear.

| Word | Plain meaning |
|---|---|
| **Container** | A packaged app with everything it needs to run (code + libraries), built once and run anywhere. Ankify is shipped as a container. |
| **Image** | The "recipe" file a container is started from. You build an image, then run it as one or more containers. |
| **Docker** | The most common tool to build and run containers. |
| **ECR** | "Elastic Container Registry." AWS's private storage for your container images. You push an image there; the hosting service pulls it from there. |
| **VPS / Instance** | A virtual computer you rent. You log in (SSH) and do anything a normal Linux machine can do. "Instance" is the AWS word for one of these. |
| **Fargate** | AWS's way of running a container **without** giving you a computer to manage. You hand AWS the image; AWS runs it. You never log into the underlying machine. |
| **ECS** | "Elastic Container Service." AWS's system for running containers. It can run them on Fargate (no machine to manage) or on EC2 machines you manage. ECS Express always uses Fargate. |
| **EC2** | A raw virtual computer from AWS (the general-purpose VPS). More settings and more flexible than Lightsail, but more complex billing. |
| **Load balancer / ALB** | A traffic entry point that sits in front of your app, ends the HTTPS connection, and forwards requests to it. "ALB" = Application Load Balancer. It is a separate paid service. |
| **TLS / HTTPS** | The lock in the browser. A "certificate" proves your domain is really yours and encrypts traffic. |
| **ACM** | "AWS Certificate Manager." AWS's free service that creates and renews TLS certificates for AWS services. |
| **DNS** | The phone book of the internet. It turns a name like `ankify.dev` into an address. |
| **Hosted zone** | One domain's set of DNS records, stored at a DNS provider (Route 53 or Cloudflare). |
| **A record** | A DNS record that points a name straight at an IP address (a number like `1.2.3.4`). |
| **CNAME record** | A DNS record that points a name at **another name** (e.g. point `mcp.ankify.dev` at `something.awsapprunner.com`). |
| **Apex / root domain** | The bare domain with nothing in front: `ankify.dev` (as opposed to `mcp.ankify.dev`). Plain DNS does not allow a CNAME here — this causes a common problem, explained in §8. |
| **Scale to zero** | The app stops running (and stops costing money) when nobody uses it, and starts again on the next request. |
| **Cold start** | The delay on the first request after the app was stopped, while it starts up again. |

---

## 2. The one idea that makes everything click

There are **two different kinds of hosting**, and your questions mix them. Once you see
the split, the rest is easy.

```
  KIND A — "Managed container"                 KIND B — "A computer you rent"
  You give AWS an image. AWS runs it.          You get a Linux machine. You run things.
  You never log into a machine.                You log in (SSH) and do anything.

   ├─ ECS Express   (uses Fargate)              ├─ Lightsail Instance  (a simple VPS)
   └─ Lightsail Container Service               └─ EC2 Instance        (the raw VPS)
```

- **Kind A (managed container)** is less work day to day. AWS keeps the machine patched,
  gives you HTTPS, and restarts the app if it crashes. You only manage your container.
  The cost: you cannot "log into the server" and run other programs on it. It runs your
  container and nothing else.

- **Kind B (a computer you rent)** is the most flexible. It **is** a full Linux computer.
  You can run your app, several other websites, a database, and a coding agent like
  Claude Code, all on the same machine. The cost: you are now the system administrator.
  You install and update software, and you set up HTTPS yourself.

Your "can I run several websites / a remote PC / Claude Code" questions are really
**Kind B** questions. Your "simplest way to host Ankify" question is a **Kind A** question.
That is why this guide covers three options, not two:

1. **ECS Express** — Kind A (managed container)
2. **Lightsail Container Service** — Kind A (managed container)
3. **Lightsail Instance** — Kind B (a computer you rent) ← this is the "remote PC" answer

---

## 3. The three options, one by one

### 3.1 ECS Express (managed container)

**What it is.** A 2025 AWS feature that takes your container image and, in one step,
sets up everything needed to run it on the internet: a Fargate service to run the
container, an Application Load Balancer (ALB) for HTTPS, autoscaling, security rules,
and logs. AWS calls it "Express" because it hides most of those parts behind one action.

```
   internet ──HTTPS──▶  Application Load Balancer  ──▶  Fargate task (your container)
                        (~$20/month, always on)         (~$9/month if always on)
```

**Cost (Frankfurt, near-idle):**

- The ALB: **about $20–26/month**, on all the time. This is the big cost. See §4 for why.
- One small Fargate task (0.25 vCPU / 0.5 GB): **about $9/month** if it runs all the time.
- ECS Express itself is free. You pay for the parts above.
- **Realistic minimum: about $25–35/month** for one always-on service.

**Custom domain:** not automatic. You create an ACM certificate in `eu-central-1`, add a
rule on the load balancer for your domain, and point DNS at the load balancer. A few
manual steps. (Details in §8.)

**Request timeout:** the load balancer cuts off requests after 60 seconds by default, but
you can raise this (up to about 4000 seconds). This matters for Ankify, whose text-to-speech
requests can take 30–60 seconds. Raise the timeout to 120–180 seconds and you are safe.

**Scale to zero?** Not by default. It keeps at least one task running. You can force the
task count to zero, but the load balancer keeps billing anyway, and the first request after
idle waits 20–60 seconds for a new task to start. So scale-to-zero does not really save you
money here, because the load balancer is the main cost.

**Remote PC?** No. ECS Express runs on Fargate, which is "managed container" (Kind A). There
is no machine to log into.

### 3.2 Lightsail Container Service (managed container)

**What it is.** Lightsail is AWS's "simple" product line. Its Container Service is the
easiest managed-container option: you give it an image, and it gives you an HTTPS address
with a working certificate, with no load balancer and no certificate work on your side.

```
   internet ──HTTPS──▶  Lightsail Container Service  (HTTPS + cert built in)
                        flat $7/month (Nano)            runs your container
```

**Cost (flat, same in all regions):**

| Tier | vCPU | RAM | Price/month |
|---|---|---|---|
| **Nano** | 0.25 | 512 MB | **$7** |
| Micro | 0.25 | 1 GB | $10 |
| Small | 0.5 | 1 GB | $15 |
| Medium | 1 | 2 GB | $40 |
| Large | 2 | 4 GB | $80 |

The price is per "node." For one small app you use one node. 500 GB/month of data
transfer is included. There is **no separate load balancer cost** — HTTPS is built in.

**Custom domain:** the simplest of all three. You ask Lightsail for a certificate, prove
you own the domain with one DNS record, and attach it. No ACM, no load balancer, no
CloudFront. Up to 4 custom domains per service.

**Request timeout — the important warning for Ankify.** The public address cuts off long
requests. AWS does not publish the exact value, but it is commonly reported as about
**60 seconds**, and **you cannot change it**. Ankify's text-to-speech requests can take
30–60 seconds, which sits right at that limit. This is the main reason this option is risky
for Ankify as it works today. It becomes safe only if you change the tool so the request
returns quickly (for example: start the job, return an id, and let the client ask for the
result a moment later).

**Scale to zero?** No. You pay the flat price all the time.

**Remote PC?** No. It is a managed container (Kind A).

**Several public apps?** One service shows **one** container to the internet (it can run up
to 10 containers, but only one is public). So "three separate public websites" means three
services (about $7 each), or one front container that routes to the others.

### 3.3 Lightsail Instance (a computer you rent) — the "remote PC"

**What it is.** A normal Linux computer in the cloud. You log in over SSH and it behaves
like any Linux machine. This is the option that answers most of your "what else can I do"
questions, because it can do anything a computer can do.

```
   internet ──▶ Lightsail Instance (a Linux computer at a fixed IP address)
                 ├─ reverse proxy (Caddy/nginx)  → ankify.dev      (your MCP server)
                 │                                → blog.you.dev    (a website)
                 │                                → app2.you.dev    (another app)
                 ├─ Docker (run any containers)
                 ├─ a database
                 └─ Claude Code, Node.js, Python, your dev tools
```

**Cost (flat, Linux, with a public IPv4 address):**

| Price/month | RAM | vCPU | SSD disk | Data transfer included |
|---|---|---|---|---|
| **$5** | 512 MB | 2 | 20 GB | 1 TB |
| $7 | 1 GB | 2 | 40 GB | 2 TB |
| $12 | 2 GB | 2 | 60 GB | 3 TB |
| $24 | 4 GB | 2 | 80 GB | 4 TB |
| $44 | 8 GB | 2 | 160 GB | 5 TB |

There are slightly cheaper plans (from $3.50) that have no IPv4 address (IPv6 only) — avoid
those unless you know you need only IPv6. The **first 3 months are free** on the $5, $7, and
$12 plans (one per account). Storage and data transfer are included in the price, which makes
the bill simple and predictable.

**What you can run on it:** anything. Several websites at once (put a reverse proxy like
Caddy or nginx in front, and it sends each domain to the right app). Docker containers. A
database. A coding agent like Claude Code. A development environment. All on one machine.

**Custom domain:** you give the instance a fixed IP address ("static IP," free while attached),
point your domain's A record at that IP, and set up HTTPS yourself. The easy way to do HTTPS
is **Caddy**, a web server that gets and renews free Let's Encrypt certificates automatically —
you write about three lines of config and HTTPS just works. (`nginx` + `certbot` is the older
manual way.) There is no built-in managed certificate like the container service has; this is
the main extra task you take on with an instance.

**Request timeout:** you control it. You run the reverse proxy, so Ankify's 30–60 second
text-to-speech requests are no problem. This removes the timeout risk that the Lightsail
Container Service has.

**The trade-off:** you are now the administrator. You install security updates, you set up
HTTPS, and if the machine has a problem everything on it is affected. For a hobby setup this
is manageable, and Claude Code can help you write the server configuration. But it is real
work that the managed options do for you.

---

## 4. Why is the ALB so expensive?

This is the key cost question, so it gets its own section.

**What the ALB does.** An Application Load Balancer is a managed front door. It accepts the
HTTPS connection from the internet, ends the encryption, checks that your app is healthy, and
forwards the request to it. It can also send different domains or paths to different apps.

**Why it costs about $20/month even at zero traffic.** The ALB bills in two parts:

1. **An hourly charge that never stops.** In Frankfurt it is **$0.027 per hour**. It is charged
   every hour the load balancer exists, whether or not anyone uses it. Over a month
   (about 730 hours) that alone is **$0.027 × 730 ≈ $19.71**.
2. **A usage charge ("LCU").** $0.008 per "capacity unit" per hour, based on how much traffic
   flows. For a near-idle hobby app this is small, but it never quite reaches zero, so you add
   a few dollars. Total realistic minimum: **about $20–26/month**.

**The thing to understand:** the cost is the *hourly* charge, not your traffic. You are renting
the front door 24 hours a day. A hobby app that gets ten requests a day pays almost the same as
a busy app, because both rent the door for the same number of hours. Only deleting the load
balancer stops the charge.

**This is why the ALB feels wrong for one small app.** It is built to be **shared**. One ALB can
sit in front of many apps and route each domain to the right one. Then the $20/month is split
across all of them, and the per-app cost becomes small. For a single tiny app, you are paying
the full $20 for a tool meant to serve dozens.

**Good news for ECS Express:** it does exactly this sharing for you. Up to **25 ECS Express
services in the same network share one load balancer** (it routes by domain name). So if you run
your MCP server plus two more services on ECS Express, they share that one ~$20 load balancer
instead of paying for three. This makes ECS Express much more reasonable once you run several
things, and expensive if you run only one.

**Why Lightsail does not have this cost.** The Lightsail Container Service has its own small
load balancer built into the flat $7 price, so there is no separate ALB bill. A Lightsail
Instance does not use an ALB at all — the machine has its own IP address and you run the reverse
proxy on it yourself.

**Cheaper ways to expose a container without an ALB** (and why they are usually not worth it):

- **Give the Fargate container a public IP directly (no load balancer).** Possible, but you lose
  managed HTTPS (you must handle certificates inside the container), the IP changes every time the
  container restarts (so DNS breaks), and there is no health checking. A public IPv4 address also
  now costs about $3.65/month on its own. Fragile.
- **Use a Network Load Balancer (NLB) instead.** Not meaningfully cheaper (same $0.027/hour base),
  and it works at a lower level, so it cannot route by domain or path. No real win.

So within the "ECS / Fargate" world, the honest options are: pay for the ALB (and share it across
several services to justify it), or switch to Lightsail where there is no separate ALB cost.

---

## 5. Running several apps at once

You asked whether you can run several websites and MCP servers at the same time. Yes, with all
three options, but the shape is different.

**ECS Express — many services, one shared load balancer.**

```
                         ┌──▶ Fargate service A   (ankify.dev)
   one shared ALB ───────┼──▶ Fargate service B   (other-app.dev)
   (~$20/month total)    └──▶ Fargate service C   (third-app.dev)
```

Each app is its own ECS Express service (its own container, its own scaling). They share one
load balancer, which routes by domain name. Up to 25 services share one ALB. **Cost:** one
~$20 load balancer for the group, plus about $9/month per always-on small task. So three services
is roughly $20 + 3 × $9 ≈ **$47/month**. The load balancer cost is shared; the per-app compute is not.

**Lightsail Container Service — one app per service.**

Each service shows one container to the internet. Three public apps = three services ≈ **$21/month**
($7 each). Simple, but the timeout limit applies to each, and they do not share anything.

**Lightsail Instance — many apps on one machine.**

```
   one $12–24/month instance
     └─ reverse proxy ─┬─ ankify.dev      → MCP server
                       ├─ blog.you.dev    → a website
                       └─ app2.you.dev    → another app
```

You run all of them on one rented computer. A reverse proxy (Caddy or nginx) reads the incoming
domain and sends it to the right app. **Cost:** one flat instance price for everything (pick a size
with enough RAM, for example $12 or $24). This is usually the cheapest way to run several small
things, and the most flexible, in exchange for managing the machine yourself.

**Summary:** for several small apps, the Lightsail Instance is normally cheapest and most flexible.
ECS Express is the cleaner "managed" choice for several services once you accept the load balancer
cost. Three separate Lightsail Container Services is simple but adds up and keeps the timeout risk.

---

## 6. A remote PC for Claude Code and dev work

You asked whether you can have a remote computer to run a development environment and a coding agent
like Claude Code. Yes — but **only with a "computer you rent" (Kind B), not a managed container.** A
managed container runs your one app and gives you no machine to log into.

**Best option: a Lightsail Instance.** It is a normal Linux computer. You SSH in, install Node.js,
Python, git, and Claude Code, and work as you would on any Linux box. It has a flat, predictable price
and 3 free months. For real coding work, pick **2–4 GB of RAM** ($12 or $24/month) — the 512 MB plan is
too small for a coding agent and builds.

**Alternative: an EC2 instance.** EC2 is the raw, general-purpose virtual computer. It can be cheaper —
there is a free trial of the `t4g.small` size (2 GB RAM) that gives **750 free hours/month until
December 31, 2026**, which covers one always-on machine. But EC2 billing is more complex: the disk and
the outgoing data transfer are billed separately, so a "cheap" instance can cost more than you expect.
For a beginner, Lightsail is the simpler choice; EC2 is worth it mainly to use that free trial.

**What about a ready-made dev environment in the browser?** AWS used to offer Cloud9 (a browser code
editor) and CodeCatalyst Dev Environments. **Both are now closed to new customers** (Cloud9 since
July 2024, CodeCatalyst since November 2025). AWS still has **CloudShell**, a free browser terminal, but
it is a light tool for quick commands, not a place to keep a real project and run an agent. So in 2026,
the practical answer for "a remote dev PC on AWS" is a Lightsail or EC2 instance you SSH into. There is
no managed, sign-up-today dev environment to recommend.

**One note:** running Claude Code on a remote instance is just "install a CLI tool on a Linux box." The
instance does not need to be the same one that hosts Ankify — though it can be, since one instance can do
both.

---

## 7. How much easier is Lightsail?

You made a fair point: if Claude Code can generate the infrastructure code (the CDK) for you, does the
extra complexity of ECS still matter? Partly yes, partly no.

**Where generated code removes the pain:** writing the configuration. ECS Express needs a load balancer,
a certificate, listener rules, IAM roles, networking, and the service itself. Writing all that by hand is
slow and error-prone. Claude Code can produce it, which removes most of that first-time burden. This is a
real and large help.

**Where complexity still costs you, even with generated code:**

- **More parts means more to understand when something breaks.** When a request fails, you have to know
  whether the problem is the load balancer, the certificate, the security rules, the task, or the network.
  With Lightsail there are far fewer parts, so there is less to check.
- **Some steps are still manual in ECS Express.** Attaching a custom domain is done by hand (create the
  certificate, add the listener rule, point DNS). It is not part of the generated code today.
- **More concepts to learn.** ECS asks you to understand Fargate, load balancers, target groups, listener
  rules, IAM roles, and VPC networking. Lightsail asks you to understand "a container service" or "a Linux
  machine." For a beginner that difference is large.

**Honest summary:** generated infrastructure code shrinks the gap, but does not erase it. Lightsail is
still simpler to understand, to run day to day, and to fix when it breaks. ECS gives you more power and
the shared-load-balancer cost benefit once you run several services. If your goal is "get this working and
not think about it," Lightsail wins. If your goal is "run several services the AWS-standard way and grow
into it," ECS is a reasonable investment of learning time.

---

## 8. Domain names, and Route 53 vs Cloudflare

### 8.1 How a custom domain works, in each option

A custom domain needs two things: **DNS** (point the name at your app) and **HTTPS** (a certificate so
the browser trusts it). Here is how each option handles both:

| | DNS step | HTTPS / certificate |
|---|---|---|
| **ECS Express** | Point your domain at the load balancer (Route 53 ALIAS, or a CNAME at Cloudflare). | You create an ACM certificate in `eu-central-1` and attach it to the load balancer. A few manual steps. |
| **Lightsail Container Service** | Point your domain at the service. | Built in. Ask Lightsail for a certificate, prove ownership with one DNS record, attach. Easiest of the three. |
| **Lightsail Instance** | Point an A record at the instance's fixed IP. | You set it up. Caddy gets and renews a free Let's Encrypt certificate automatically. Most manual, but Caddy makes it short. |

### 8.2 The apex domain problem (why `ankify.dev` is harder than `mcp.ankify.dev`)

A normal DNS rule says you cannot put a CNAME (a "point at another name" record) on the bare root domain
(`ankify.dev`). You can put one on a subdomain (`mcp.ankify.dev`). This matters because AWS gives you a
*name* to point at (like a load balancer hostname), not an IP, and you cannot CNAME the root to it.

Two ways around it:

- **Cloudflare "CNAME flattening":** Cloudflare lets you enter a CNAME on the root domain and quietly turns
  it into the right answer. This works on Cloudflare's free plan, with no extra steps.
- **Route 53 "ALIAS" record:** Route 53 has a special record type that points the root domain straight at an
  AWS resource (load balancer, CloudFront, App Runner). It is free to query when it points at an AWS resource.

**The simplest fix for a beginner:** use a subdomain like `mcp.ankify.dev`. A plain CNAME works there at any
DNS provider, and you avoid the whole apex problem.

### 8.3 Route 53 vs Cloudflare — should you move everything to AWS?

**What each costs:**

- **Route 53:** $0.50 per domain per month, plus $0.40 per million DNS lookups. But lookups for ALIAS records
  that point at AWS resources are **free**, so for a small app the real cost is about **$0.50/month**.
- **Cloudflare DNS:** **free.** Unlimited records and lookups. It also includes a free CDN, caching, and
  basic DDoS protection.

**Does "everything on AWS" make sense?** Not really, and you do not need it. Running your app on AWS while
keeping DNS at Cloudflare is a normal, common setup. Mixing the two is fully supported. Reasons to keep
Cloudflare: it is free, it handles the apex domain for you (CNAME flattening), and it adds a free CDN and
DDoS protection. Reasons to move to Route 53: you want everything in one console, or you want Route 53's
health checks and failover features. For a hobby app, **keep Cloudflare.**

**One gotcha if you keep Cloudflare with an AWS certificate.** Cloudflare can "proxy" your traffic (the
orange-cloud icon). When you are validating an AWS ACM certificate, the proxy gets in the way and validation
fails. Set those DNS records to **"DNS only" (the grey-cloud icon)** during certificate setup. This is the
single most common Cloudflare-plus-AWS mistake.

---

## 9. Recommendation

There is no single "best." It depends on what you want. Here is how I would choose, given what you said.

**If you want to run several small things AND have a box to run Claude Code on → Lightsail Instance (VPS).**
One $12–24/month Linux machine can host Ankify, host other websites and containers, and be your remote
development box for Claude Code, all at once. It avoids the load balancer cost, it avoids the container
timeout limit (you control the reverse proxy, so Ankify's long requests are fine), and the bill is one flat,
predictable number. The price is that you manage the machine: updates, and HTTPS via Caddy. For someone
curious to do several things, this is the most useful single answer, and it doubles as a way to learn Linux
server basics with Claude Code helping you.

**If you want AWS to manage the containers and you will run several services → ECS Express.**
This is the "proper" AWS way and a good thing to learn. The shared load balancer means several services split
the ~$20 cost, which is the only way that cost makes sense. You give up the "remote PC" ability, you do the
custom-domain steps by hand, and you accept about $25–35/month for one service or roughly $47/month for three.
Raise the load balancer timeout to 120–180 seconds so Ankify's text-to-speech requests are safe.

**If you want the simplest possible managed option for Ankify alone → Lightsail Container Service ($7).**
Cheapest managed choice, easiest HTTPS and domain setup. **But** its ~60-second request timeout sits exactly
on top of Ankify's 30–60 second text-to-speech requests, and you cannot change it. Only choose this if you
first change the tool to return quickly (start the job, return an id, fetch the result later), or if you are
sure your requests stay short.

**A practical path:** start with a **Lightsail Instance** at $12/month (2 GB RAM, free for 3 months). Run Ankify
on it with Caddy for automatic HTTPS, point `mcp.ankify.dev` (a subdomain, to skip the apex problem) at its IP
through Cloudflare, and use the same machine to try Claude Code and any other small apps. If you later want
AWS to manage things for you, or you outgrow one machine, move to ECS Express then — you will understand the
trade-offs much better by that point.

---

## 10. Side-by-side comparison

| | **ECS Express** | **Lightsail Container** | **Lightsail Instance (VPS)** |
|---|---|---|---|
| **Kind** | Managed container | Managed container | A computer you rent |
| **You manage the OS?** | No | No | Yes |
| **Minimum cost/month (Frankfurt)** | ~$25–35 (1 service) | $7 flat (Nano) | $5–24 flat |
| **Load balancer cost** | ~$20, shared across up to 25 services | None (built in) | None (you run the proxy) |
| **HTTPS / custom domain effort** | Manual: ACM cert + rule + DNS | Easiest: built-in cert | You set it up (Caddy makes it easy) |
| **Request timeout vs Ankify's 30–60s** | Configurable to 120–180s — safe | ~60s, not changeable — risky | You control it — safe |
| **Run several apps?** | Yes, share one load balancer | One public app per service | Yes, many on one machine |
| **Remote PC / run Claude Code?** | No | No | **Yes** |
| **Scale to zero (stop paying when idle)?** | No (load balancer always bills) | No (flat price) | No (flat price) |
| **Learning curve for a beginner** | Higher | Low | Medium (Linux basics) |
| **Best for** | Several managed services, the AWS-standard way | One simple app with short requests | Several small things + a dev box |

---

## 11. Sources

Checked 2026-06-16. Prices are for `eu-central-1` (Frankfurt) where region matters; Lightsail prices are the
same in most regions.

- ECS Express Mode — shared load balancer (up to 25 services), Fargate only, custom-domain steps, default of at
  least one running task, ~20–60s cold start:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html and
  https://aws.amazon.com/blogs/aws/build-production-ready-applications-without-infrastructure-complexity-using-amazon-ecs-express-mode/
- Application Load Balancer pricing ($0.027/hour + $0.008/LCU-hour in Frankfurt; billed continuously):
  https://aws.amazon.com/elasticloadbalancing/pricing/
- Public IPv4 address charge (~$3.65/month): https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/
- Lightsail pricing (container service tiers, instance tiers, included data transfer, 3 free months):
  https://aws.amazon.com/lightsail/pricing/
- Lightsail container service capabilities (built-in HTTPS, custom domains, one public container per service,
  no scale to zero): https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html
- Lightsail instance HTTPS with Caddy/Let's Encrypt/Certbot, static IP behavior:
  https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-using-lets-encrypt-certificates-with-nginx.html
- Route 53 pricing ($0.50/zone/month, $0.40/million queries, free ALIAS to AWS resources):
  https://aws.amazon.com/route53/pricing/
- Cloudflare CNAME flattening (free, solves the apex problem): https://developers.cloudflare.com/dns/cname-flattening/
- EC2 t4g free trial (750 hours/month of t4g.small through 2026-12-31): https://aws.amazon.com/ec2/faqs/
- AWS Cloud9 closed to new customers (2024): https://docs.aws.amazon.com/cloud9/latest/user-guide/history.html
- AWS CodeCatalyst closed to new customers (2025): https://aws.amazon.com/codecatalyst

**Lower-confidence items to verify yourself before relying on them:**

- The exact Lightsail Container Service request timeout. AWS does not publish it. Community reports point to about
  60 seconds and say it cannot be changed. Treat it as a real risk for long requests, not an exact number.
- Pulling images from a private ECR repository into a Lightsail Container Service is supported but needs a specific
  "private registry access" setting. Confirm the current steps in the Lightsail docs before depending on it.
- EC2 dollar figures are based on US pricing; Frankfurt is a few percent higher. Re-check for your region and date.

---

## 12. Which of these scales, and which auto-scales?

There are two kinds of scaling, and a separate question of whether the platform does it for you:

- **Vertical scaling** = give the same app a bigger machine (more CPU and RAM).
- **Horizontal scaling** = run more copies of the app behind a load balancer, so they share the work.
- **Automatic?** = does the platform add and remove capacity on its own when traffic changes, or do you change a setting by hand?

Here is where each option stands:

| Option | Vertical (bigger) | Horizontal (more copies) | Automatic? | Scale to zero |
|---|---|---|---|---|
| **ECS Express** | Change the task size (a redeploy) | Yes, built in | **Yes — automatic**, on load | No (the load balancer always bills; see §10) |
| **App Runner** (the other doc) | Change CPU/memory | Yes, built in | **Yes — automatic**, when in-flight requests pass `MaxConcurrency` | No (manual pause only) |
| **Lightsail Container** | Change the "power" (size) | Change the "scale" (1–20 nodes) | **No — manual.** You change the number; it does not react to load | No |
| **Lightsail Instance / any VPS (incl. Hetzner)** | Resize the plan (stop, resize, start; usually cannot shrink the disk again) | You build it yourself (more machines + your own load balancer) | **No** | No |

**Short version:**
- **Auto-scaling (no work from you): ECS Express and App Runner only.** Both add and remove instances automatically based on load. This is the main thing these "managed container" options give you over a rented computer.
- **Manual scaling: Lightsail Container** (you set power and node count) **and any VPS** (you resize the plan). Nothing reacts to traffic on its own.
- **Scale to zero:** effectively none of them here. App Runner's pause and Fly.io (see §13) are the closest, both with a cold start. This is already covered in §10.

**What this means for Ankify in practice.** Ankify is a low-traffic tool with rare overlapping requests. You will almost never need a second instance, so automatic horizontal scaling is a feature you are unlikely to use. The first limit you actually hit is **not** "too many requests at once" — it is one of:
1. a single long text-to-speech request using the one small CPU for 30–60 seconds, so a second request waits; or
2. memory during a build or deploy.

Auto-scaling solves neither of those well — a slightly bigger single box does. So treat auto-scaling as a "nice to have if you grow into many users," not a deciding factor for a hobby tool.

---

## 13. Are there much cheaper providers than AWS?

**Short answer:** yes for the "rent a computer" kind — **Hetzner is about 3–4× cheaper than AWS Lightsail** for the same RAM. For the "managed container" kind the savings are smaller. But read the catch first, because the server price is not the whole story.

### 13.1 The catch: leaving AWS means losing the integrated services

The server price is not the main reason this project is on AWS. Ankify leans on AWS **managed services**: S3 (deck files), Secrets Manager (the Azure key), optionally Polly (one TTS voice), and optionally Cognito + DynamoDB (login). On AWS the server is given permission to use these through an **IAM role**, so there are **no passwords stored on the box**.

Move the server to Hetzner or any non-AWS host, and for each of those services you have two choices: keep calling it over the internet (which now needs a **static AWS access key** on the box — a long-lived password to guard and rotate, a step down in security), or replace it with something local. For Ankify, replacing is usually easy:

| AWS piece today | Used for | Simplest off-AWS replacement |
|---|---|---|
| S3 + presigned URL | Store and hand out `.apkg` files (1-day expiry) | Serve the file from local disk through Caddy, with a daily cleanup job; or Cloudflare R2 (S3-compatible, no egress fee) |
| Secrets Manager | The Azure TTS key | An environment variable / `.env` file on the box (the project already uses `ANKIFY__` env vars) |
| Polly (AWS TTS) | One TTS voice option | Drop it; Azure TTS (already the main provider) or Edge TTS (free) need no AWS |
| Cognito + DynamoDB | Optional OAuth login + its state | Cloudflare Access or self-hosted Authentik in front; or keep Cognito over the internet; SQLite/Postgres for state |
| IAM role credentials | Permission with no stored key | Gone; if you keep any AWS service you store a static access key instead |

**Bottom line of the catch:** Ankify can run fully off AWS without much trouble (local disk for decks, env var for the key, Azure or Edge for voices). What you give up is the convenience of AWS holding your secrets and handing out credentials automatically. If you specifically want to keep S3 or Cognito, the price is managing a static key on the box.

### 13.2 "Rent a computer" prices (this is where the big saving is)

About 4 GB RAM, 2 vCPU, EU region (close to your `eu-central-1` Frankfurt and Azure `westeurope`, so latency to Azure TTS stays low):

| Provider | Plan | vCPU | RAM | Disk | Traffic incl. | Price/month |
|---|---|---|---|---|---|---|
| **AWS Lightsail** | 4 GB | 2 | 4 GB | 80 GB | 4 TB | **$24** |
| **Hetzner** | CAX11 (ARM) | 2 | 4 GB | 40 GB | 20 TB | **~€6 (~$6.50)** + VAT |
| **Hetzner** | CX23 (Intel) | 2 | ~4 GB | ~40 GB | 20 TB | **~€5.5 (~$6)** + VAT |
| DigitalOcean | 4 GB | 2 | 4 GB | 80 GB | 4 TB | $24 |
| Vultr / Akamai (Linode) | 4 GB | ~2 | 4 GB | ~80 GB | ~4 TB | ~$24 |

**Reading:** Hetzner is roughly 3–4× cheaper than Lightsail for the same RAM, and includes far more traffic (20 TB). **DigitalOcean, Vultr, and Linode (now Akamai) cost about the same as Lightsail** — they are *not* substantially cheaper. Among the well-known names, **Hetzner is the one real price win.** A note on ARM: the project already builds **arm64** images, so Hetzner's ARM line (CAX) runs them directly. But since the 15 June 2026 price change, Hetzner's x86 line (CX) is cheaper, and adding an x86 build is easy — so CX is the better default (see §17.1).

Two more, with honest caveats:
- **Contabo** — even cheaper headline prices (a lot of RAM for the money), but a weaker reputation for performance, support, and network reliability. Fine for non-critical hobby use, not for something you depend on.
- **Oracle Cloud "Always Free"** — a genuinely free ARM allowance (up to 4 ARM cores and 24 GB RAM total). The catch is real: free capacity is often unavailable in popular regions, and idle free accounts have been reclaimed. Good if you can get it and accept that risk.

### 13.3 "Managed container" prices (smaller saving)

If you want the platform to run the container for you (no Linux admin), the non-AWS options are Fly.io, Render, and Railway. The saving here is smaller than the VPS win:

| Option | Price (small app) | Scale to zero | Fit for Ankify's 30–60s requests |
|---|---|---|---|
| ECS Express | ~$25–35/mo | No | Safe (raise the timeout) |
| Lightsail Container | $7/mo flat | No | Risky (~60s fixed timeout) |
| **Fly.io** | pay-per-use; ~$2–5/mo for a small always-light app, near $0 if it sleeps | **Yes** (cold start ~0.3–2s) | You control it — safe |
| Render | $7/mo (paid web service) | No on paid; free tier sleeps | Paid: ok. **Free tier cold start (30–60s) is bad here** |
| Railway | usage-based, ~$5/mo credit on Hobby | No | You control it — ok |

**Reading:** **Fly.io** is the interesting one for a tool that sits idle most of the time — it can scale to zero with a sub-second cold start and bill almost nothing when unused, which neither ECS Express nor Lightsail Container does. The trade-off is a bit more setup than Lightsail Container. Render and Railway cost about the same as Lightsail Container ($7), so they are not a big saving; avoid Render's free tier here because its cold start lands right on top of Ankify's already-long requests.

### 13.4 Caveats — re-check before you commit money

- **VAT.** Hetzner prices exclude VAT. A private EU customer adds local VAT (19% in Germany → ~€6 becomes ~€7.1). A business with a VAT ID pays the net price.
- **Hetzner raised prices twice in 2026** — on 1 April and again on 15 June 2026. The 15 June change hit the **CPX and CCX** lines hard (up to +176%), but the **cost-optimized CX and CAX** lines stayed low and are the ones quoted above. Older comparisons that quote CPX prices are now out of date. The gap to AWS is narrowing but is still large.
- **Support and guarantees.** AWS gives you deep tooling, many regions, and paid support tiers. Hetzner and Contabo give you a cheap box and community-level support. Fine for a hobby tool; weigh it for anything you depend on.
- **Region / latency.** Hetzner's German datacenters are close to your AWS `eu-central-1` and Azure `westeurope`, so calls to Azure TTS stay fast. Good match for this project.

---

## 14. How much fits on a 2 GB machine?

The honest answer depends less on idle memory and more on **bursts, builds, and the 2 shared CPUs**. But here is a working budget.

**Idle memory budget (rough, Linux + Docker):**

| Thing | Typical idle RAM |
|---|---|
| Linux base + Docker daemon | 300–450 MB |
| Caddy or nginx reverse proxy | 15–30 MB |
| One Python web server (uvicorn + FastMCP, like Ankify) | 120–250 MB (more once TTS libraries and boto3 are loaded) |
| PostgreSQL (small, tuned) | 120–200 MB |
| Redis (small) | 10–50 MB |
| SQLite | ~0 (it runs inside the app process) |

On a 2 GB box (about 2000 MB usable) plan to use **no more than ~75–80% at steady state**, so the kernel has room for request spikes and does not start killing processes. That leaves roughly **1.4–1.6 GB** to spend.

**Realistic on 2 GB, hobby traffic:**
- **About 4–6 small Python servers** like Ankify, each with SQLite, plus a reverse proxy. (~1.5 GB ÷ ~250 MB.)
- Or **3–4 Python servers + one PostgreSQL + one Redis**, shared by all of them. Run **one** Postgres holding several databases, not one Postgres per app — far more efficient.
- **SQLite databases are effectively free** in RAM terms; you can have many. "Databases" only cost real memory when they are separate server processes (Postgres, MySQL, Redis).

**The limits you actually hit first (not idle RAM):**
1. **Request bursts.** Ankify holds audio in memory while building a deck. A few large decks at the same time spike well above idle. This, not the count of idle servers, is usually what fills 2 GB.
2. **Builds and deploys.** `uv pip install`, a Docker build, or a large dependency download can use several hundred MB to over 1 GB on their own. On a full 2 GB box a build can fail with out-of-memory. (This is why §6 says 512 MB is too small for Claude Code and builds.)
3. **CPU, not memory.** A 2 GB plan gives about 2 shared vCPUs. Ankify's TTS uses CPU heavily for 30–60s per request, so two such requests at once already compete for the CPU long before RAM runs out.

**Two cheap protections on a small box:**
- Add a **swap file** (for example 2 GB). It does not replace real RAM, but it gives headroom so a short build or burst does not trigger the out-of-memory killer. Cheap insurance.
- Put a **memory limit on each container** (Docker `--memory`) so one misbehaving app cannot take the whole machine down.

**If you also want Claude Code on the same box** (the §6 case): a coding agent plus builds can use 1–2 GB by itself while it runs. Then 2 GB is tight — step up to **4 GB** (Lightsail $24, or Hetzner CAX21 ~€10.5/mo). On Hetzner the step from 4 GB to 8 GB is cheap enough that there is little reason to crowd a 2 GB box.

**One-line answer:** a 2 GB box comfortably runs Ankify plus about **3–4 other small Python services** and their SQLite/Postgres data for hobby traffic. Add a swap file, watch bursts and builds (not idle RAM), and move to 4 GB if you also want to run Claude Code there.

---

## 15. Sources for sections 12–14

Checked 2026-06-17. Prices change often, especially Hetzner's (two increases in 2026) — re-check the official pages before you order.

- Hetzner price adjustment, 15 June 2026 (official; current CX / CAX / CPX / CCX prices, excludes VAT): https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Hetzner Cloud product and pricing page: https://www.hetzner.com/cloud/
- DigitalOcean Droplet pricing (Basic plans, per-second billing with monthly cap): https://www.digitalocean.com/pricing/droplets
- AWS Lightsail instance pricing (same numbers as §3.3): https://aws.amazon.com/lightsail/pricing/
- Fly.io pricing and scale-to-zero (`auto_stop_machines`): https://fly.io/docs/about/pricing/ and https://fly.io/docs/launch/autostop-autostart/
- Render pricing (free tier spins down with cold start; paid web service from $7): https://render.com/pricing
- Railway pricing (Hobby plan credit, usage-based): https://railway.com/pricing
- Oracle Cloud Always Free (ARM Ampere allowance): https://www.oracle.com/cloud/free/

**Lower-confidence items to verify yourself:**

- Exact Hetzner CX23 / CAX11 specs and post-15-June prices come from the official adjustment page plus third-party trackers; Hetzner renames and re-prices often, so confirm the live spec and price on hetzner.com before ordering. Prices quoted exclude VAT.
- That DigitalOcean / Vultr / Linode sit at about Lightsail's price is stable, but check the exact plan you want.
- Fly.io's "no free tier, scale-to-zero, sub-second cold start" and Render's free-tier cold-start times come from third-party 2026 summaries; confirm on each provider's own pricing page.
- The memory-footprint numbers in §14 are general engineering estimates, **not measured for this project**. Measure on your real box with `docker stats` and `free -m` before you rely on them.
- Oracle Always Free capacity availability and the account-reclamation risk are widely reported but not guaranteed; check Oracle's current terms.

---

## 16. Running a VPN server on the same VPS (e.g. on Hetzner)

You asked: can the same rented computer also run your own VPN server, and does a VPN use
"the same resources as a Python server"?

**Short answer:** yes, you can run both on one box, and no, a VPN does not use the same
amount of resources. A modern VPN (WireGuard) at rest uses **far less** RAM and CPU than the
Ankify Python server. The resource a VPN actually spends is **network bandwidth**, and only
while you are using it.

### 16.1 First, what "a VPN server" means here

"VPN" covers two different goals. Decide which one you want, because the setup differs:

- **A. Personal exit VPN.** Your laptop or phone sends *all* its internet traffic through the
  box first. To websites you appear to come from the box's IP (and country), and your traffic
  is encrypted on untrusted networks (cafe Wi-Fi, etc.). This is the "be my own NordVPN" case.
- **B. A private network to reach your own services.** The VPN is only a secure tunnel between
  your devices and the box, so you can reach private things (a database, an admin page, Ankify
  before it is public) without opening them to the whole internet. Nothing else routes through it.

Both run fine next to Ankify. They listen on a different port (WireGuard uses one **UDP** port,
by default 51820; Ankify uses HTTPS on 443 through the reverse proxy), so they do not collide.

### 16.2 Resources: a VPN is much lighter than the Python server

| Thing on the box | Idle RAM | Idle CPU | What actually costs |
|---|---|---|---|
| Ankify (uvicorn + FastMCP + TTS libs + boto3) | 120–250 MB | low, but **30–60s CPU burst per TTS request** | CPU during a request, memory while building a deck |
| **WireGuard VPN** | **~30–50 MB** | **under 1% idle** | **bandwidth**, plus some CPU only at high throughput |

WireGuard is tiny on purpose: it runs in the Linux kernel and its whole codebase is about
4,000 lines (OpenVPN is over 100,000 and is heavier per connection — avoid it here). A 2 vCPU /
4 GB box like the cheapest Hetzner plan handles a personal VPN for a handful of devices without
noticing it. So adding a VPN does **not** meaningfully change the memory budget in §14.

**The real cost is bandwidth, and only for the "exit VPN" case (A).** If all your phone and laptop
traffic flows through the box, that traffic counts against the box's included data transfer. This
is where Hetzner shines: its cloud plans include **20 TB/month**, so personal VPN use is effectively
free. On AWS Lightsail the included transfer is smaller (1–5 TB depending on plan) and overage is
billed, so a heavy exit VPN there could add to the bill. Case B (reach your own services) moves
almost no data, so bandwidth is a non-issue.

### 16.3 The simple ways to do it

- **WireGuard, with a small web UI (`wg-easy`).** Runs as one Docker container. You add devices by
  scanning a QR code. This is the common self-hosted choice. Good for both case A and case B.
- **Tailscale (or its open-source server, Headscale).** This is the easiest path for case B. It
  builds a private network between your devices using WireGuard underneath, and it handles the hard
  parts (key exchange, getting through firewalls) for you. The hosted Tailscale has a free personal
  tier. You install it on the box and on your devices, and they can reach each other — no public
  port to open. If your goal is "reach my own stuff securely," start here.

### 16.4 Things to check before you do it

- **Provider rules.** Hetzner permits running a personal VPN. Do not run an *open/public* VPN or
  exit node for strangers — that draws abuse complaints and can get the account suspended.
- **You own the exit IP.** With an exit VPN (A), anything you do online comes from the box's IP.
  If that IP gets flagged (for example, by a site that dislikes datacenter IPs), your normal
  browsing can break. Some sites block known hosting-provider IP ranges.
- **It shares the box with Ankify.** A reboot or a misconfiguration affects both. For a hobby setup
  this is fine; just remember the VPN and the app are now in the same basket.

**One-line answer to your question:** a VPN is not "the same resources as a Python server" — at idle
it is much lighter (tens of MB of RAM, almost no CPU). It only spends real resources, mainly
**bandwidth**, while you are actively routing traffic through it, and Hetzner's 20 TB allowance makes
that essentially free for personal use.

---

## 17. Hetzner VPS options in detail

§13 said Hetzner is the one real price win over AWS. This section explains which Hetzner plan to
pick and what the add-ons cost, so the bill has no surprises.

### 17.1 The product lines (and which one you want)

Hetzner Cloud has four server lines, plus a separate dedicated-server product:

| Line | CPU type | Sharing | For you? |
|---|---|---|---|
| **CX** | Intel/AMD | Shared vCPU, cost-optimized | **Yes — best fit** — cheapest at every tier (see below) |
| **CAX** | ARM (Ampere) | Shared vCPU, cost-optimized | Works, but priced above CX since June 2026 (see below) |
| CPX | AMD | Shared vCPU | Skip — the 15 June 2026 increase hit this line hard (up to +176%) |
| CCX | Dedicated vCPU | Not shared | Skip for a hobby tool — also raised a lot in June 2026, and you do not need guaranteed cores |
| (Robot dedicated servers) | Whole physical machines | — | Overkill; a different, monthly-contract product |

"Shared vCPU" means you share physical CPU cores with other tenants. For a low-traffic, bursty tool
like Ankify this is the right and cheapest choice. "Dedicated vCPU" (CCX) gives you guaranteed cores
but now costs several times more after the June increase — not worth it here.

**Why CX (x86) is the best fit for this project:** after the 15 June 2026 price change, CX is cheaper
than CAX at every tier (CX23 €5.49 vs CAX11 €5.99, and the gap grows with size — see §17.2). The only
reason to look at the ARM line is that the project builds **arm64** Docker images today, but that is not
a reason to pay more. Adding an x86 (amd64) build is a one-time task: `docker buildx build --platform
linux/amd64,linux/arm64 ...` builds both at once, and in CI the amd64 build is the native, fast path
(GitHub runners are x86, so the arm64 build is the one that needs emulation). Cross-building amd64 on an
Apple Silicon Mac is slower because it uses QEMU emulation, but that only slows the build, never the
running server, and you avoid it by building in CI or on the server itself. For a low-traffic, bursty
tool the ARM-vs-x86 performance difference does not matter. **So pick CX.** Choose CAX only if you
refuse to add an x86 build; that saves a few minutes of setup and costs €0.50–€11.50/month more, which
is not a good trade.

(Naming note: the current CX line — CX23 / CX33 / CX43 / CX53, "Gen3" — runs on **Intel or AMD**
depending on availability, not Intel only.)

### 17.2 Current prices (post-15-June-2026, Frankfurt/Falkenstein, EUR, **excluding VAT**)

**CX — x86, Intel or AMD (recommended):**

| Plan | vCPU | RAM | SSD disk | Price/month |
|---|---|---|---|---|
| **CX23** | 2 | 4 GB | 40 GB | **€5.49** |
| **CX33** | 4 | 8 GB | 80 GB | **€8.49** |
| CX43 | 8 | 16 GB | 160 GB | €15.99 |
| CX53 | 16 | 32 GB | 320 GB | €29.49 |

**CAX — ARM (costs more; pick only if you skip the x86 build):**

| Plan | vCPU | RAM | SSD disk | Price/month |
|---|---|---|---|---|
| CAX11 | 2 | 4 GB | 40 GB | €5.99 |
| CAX21 | 4 | 8 GB | 80 GB | €10.49 |
| CAX31 | 8 | 16 GB | 160 GB | €20.99 |
| CAX41 | 16 | 32 GB | 320 GB | €40.99 |

All cloud plans include **20 TB/month** of outbound traffic. Note that **even the smallest plan has
4 GB of RAM** — this removes the "2 GB is tight" worry from §14. The 512 MB / 1 GB sizes discussed there
were the small AWS Lightsail plans; on Hetzner you start at 4 GB for about €6.

### 17.3 The add-ons that change the bill

The base price is not quite the whole story. These are the extras that matter:

| Add-on | Cost | Note |
|---|---|---|
| **Primary IPv4 address** | **+€0.50/month** | Or run IPv6-only and save it — but then clients without IPv6 cannot reach you. Keep IPv4 for a public server. |
| Automatic backups | +20% of the server price | Optional. Daily snapshots kept on a rolling basis. |
| Snapshots (manual images) | ~€0.012 per GB/month | Small for one image. |
| Block-storage volume | ~€0.048 per GB/month (~€5 per 100 GB) | Only if you outgrow the included SSD. Ankify does not need one. |
| Extra traffic over 20 TB | ~€1 per TB | You will not reach 20 TB on this workload. |

So a realistic Ankify bill on Hetzner is **CX23 (€5.49) + IPv4 (€0.50) ≈ €5.99/month ex VAT**, or
**CX33 (€8.49) + €0.50 ≈ €9/month** if you also want to run Claude Code and a few other things on
the same box (the §6 / §14 case). Add VAT if you order as a private EU customer (see the §13.4 note).

### 17.4 Locations

Hetzner has datacenters in **Germany (Falkenstein, Nuremberg)** and **Finland (Helsinki)** in Europe,
plus the USA (Ashburn, Hillsboro) and Singapore. For this project pick a **German** location: it is
close to Azure `westeurope`, so calls to Azure TTS stay fast (the same reasoning as §13.4).

---

## 18. Fly.io in detail

§13.3 flagged Fly.io as the interesting "managed container" option for a tool that sits idle most of
the time, because it can scale to zero with a sub-second wake-up. This section explains how it maps to
Ankify and what it costs.

### 18.1 What Fly.io is

Fly.io runs your container as a **Machine** — a small, fast-booting virtual machine (Firecracker
microVM). You give it your image and a short `fly.toml` config; Fly runs it, gives it HTTPS, and can
stop it when idle and start it again on the next request. It runs in many regions, including
**Frankfurt (`fra`)** and **Amsterdam (`ams`)**, both close to Azure `westeurope`.

It is "managed container" (Kind A in §2): you do not log into a Linux box, so it is **not** a remote
PC for Claude Code. It only runs your app.

### 18.2 How Ankify's pieces map onto Fly.io

| Ankify needs | On Fly.io |
|---|---|
| Run the container | A Machine (`shared-cpu-1x`), billed per second |
| HTTPS + custom domain | `fly certs add ankify.dev` — automatic Let's Encrypt certificate. Apex works directly: Fly gives you real A/AAAA IPs, so there is **no apex/CNAME-flattening problem** like §8.2. |
| Secrets (the Azure key) | `fly secrets set ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY=...` — stored encrypted, injected as an env var at runtime. Fits the project's `ANKIFY__` convention. No AWS Secrets Manager needed. |
| Store `.apkg` files | **Tigris** object storage (S3-compatible, built into Fly, no egress fee) — or just serve from the Machine's disk with a cleanup job. No AWS S3 needed. |
| Long 30–60s TTS request | You control the server and timeout; Fly's edge timeout is generous. **Safe**, unlike the Lightsail Container ~60s fixed limit. |
| Scale to zero | `auto_stop_machines` / `auto_start_machines` in `fly.toml`. Stopped Machines cost **$0** for CPU and RAM. Cold start is about 1–2 seconds (a Machine resume), not the 30–60s of Render's free tier. |

### 18.3 Cost

- **`shared-cpu-1x`, 256 MB:** about **$2.02/month** if always on; **512 MB:** about **$3.32/month**.
  Billed per second, so a Machine that sleeps when idle costs a fraction of this.
- **Scale to zero:** with `auto_stop_machines` on, an idle hobby tool costs **near $0** for compute —
  you pay only for the seconds it is awake and serving.
- **Outbound bandwidth:** **$0.02/GB** in Europe/North America. Ankify's traffic is small, so this is
  cents.
- **TLS certificate:** about **$0.10/month** per hostname.
- **Volumes:** $0.15/GB/month, **and you keep paying even when the Machine is stopped**. Ankify does
  not need a volume (use Tigris or `/tmp`), so avoid volumes to keep the scale-to-zero saving real.
- **No free tier for new accounts** since late 2024 — it is pay-as-you-go, with a small trial credit.

**Realistic Ankify bill on Fly.io:** with scale-to-zero, **roughly $0–3/month**. A small always-on
Machine is about **$2–3.50/month** plus a few cents for the certificate and traffic. This is the
cheapest *managed* option that also handles the long TTS request safely.

### 18.4 The catch (same shape as §13.1)

Fly.io is not AWS, so you lose the IAM-role convenience: there are no automatic AWS credentials on the
Machine. For this project that is mostly fine, because Fly replaces the AWS pieces cleanly — **Tigris**
for S3, **`fly secrets`** for Secrets Manager, **Azure or Edge TTS** for voices (no Polly). The one
piece that needs a decision is login: AWS Cognito would have to be reached over the internet with a
static AWS access key on the Machine, or you switch to a provider-neutral login like Auth0 (see §19).

**When to pick Fly.io:** you want a managed container (no Linux admin), you want it to cost almost
nothing while idle, and you are willing to learn one more platform and move the deck storage off S3.
If instead you want a box you can also SSH into and run Claude Code on, that is the Hetzner/Lightsail
instance case (§6, §17), not Fly.io.

---

## 19. OAuth in detail: Cognito, Auth0, Cloudflare, or local

You asked which login option to use. The honest first question is **whether you need full OAuth at
all** for a single-user hobby tool — often a simple shared token is enough (see the end of this
section). But here is the full comparison, framed around what MCP and FastMCP actually need.

### 19.1 The MCP angle (why this is not a free choice)

An MCP client (Claude Desktop and similar) logs in through a **browser OAuth flow** and then sends a
token with each request. So the server needs a login provider that **FastMCP can wrap**. The good news:
FastMCP 3.x (which the project already runs) has **built-in providers** for AWS Cognito, Auth0, Google,
GitHub, Azure/Entra, WorkOS, Descope, and Scalekit, plus generic OIDC and JWT verifiers. So Cognito and
Auth0 are both first-class; Cloudflare Access works differently (it sits in front, not inside); "local"
means either FastMCP's own token verifier or a self-hosted OIDC server.

### 19.2 The four options compared (for this project)

| Option | How it works with FastMCP | Free tier | Ties you to AWS? | Best when |
|---|---|---|---|---|
| **AWS Cognito** | Built-in `AWSCognitoProvider` (already specced in the deployment spec §7). Needs DynamoDB for state and a fixed signing key. | 10,000 MAU | **Yes** — clean on AWS via the IAM role; on a non-AWS host it needs a static AWS access key on the box | You stay on AWS (App Runner / ECS / EC2) |
| **Auth0** | Built-in `Auth0Provider` (OIDC). Just `client_id` + `client_secret` in env. No AWS dependency. | 25,000 MAU | No — works the same on AWS, Hetzner, or Fly | You leave AWS but still want standards-based per-user login |
| **Cloudflare Access** | **Not** a FastMCP provider — it is a gate *in front* of the server (see 19.3) | Up to 50 users | No | Your DNS is already at Cloudflare and you mainly want to lock the server to yourself |
| **Local / self-hosted** | FastMCP's own JWT/static-token verifier, **or** a self-hosted OIDC server (Keycloak, Authentik) via the OIDC proxy | No MAU limit (you run it) | No | "Just me" (static token), or you want full ownership and many users (Keycloak) |

### 19.3 Cloudflare Access is different — read this before choosing it

Cloudflare Access does not give your app an OAuth login. It is a **zero-trust proxy**: it checks
identity *before* a request reaches your server. With an MCP client there are two modes, and the
trade-off matters:

- **Interactive login (browser OAuth).** True per-user identity, but the flow is awkward for an MCP
  client that connects programmatically.
- **Service token** (a `CF-Access-Client-Id` + `CF-Access-Client-Secret` pair sent as headers). This
  works cleanly for MCP clients — you put the pair in the client config. But it is a **shared secret,
  not per-user identity**: everyone using that token looks the same, and there is no per-user audit.

So Cloudflare Access is "lock the whole door with a key," not "each user logs in with their own face."
For a single-user hobby tool that is often exactly what you want, and it needs **no FastMCP auth code
at all** — you turn it on at Cloudflare and add the service token to the client. It does **not** give
the standards-based, per-user MCP OAuth that Cognito and Auth0 do.

### 19.4 "Local" — two meanings

- **FastMCP static / JWT token (simplest).** You issue a bearer token; the client sends it. No login
  UI, no external service, no MAU limit, nothing to run. Good for "only I use this." You manage and
  rotate the token yourself.
- **Self-hosted OIDC server (Keycloak or Authentik).** A real login server you run on the box and wrap
  with FastMCP's OIDC proxy. Full control and no per-user fee, but it is another service to run, secure,
  and update, and it uses real RAM (a few hundred MB). Worth it only if you want many users and full
  ownership — overkill for a hobby tool.

### 19.5 Recommendation

- **Staying on AWS → Cognito.** It is already designed in the deployment spec, free at this scale, and
  needs no stored AWS key (the IAM role handles credentials).
- **Moving to Hetzner or Fly.io and you want per-user OAuth → Auth0.** It is provider-neutral, has a
  large free tier, and needs only a client id and secret in the environment — no static AWS key, no
  DynamoDB-for-AWS-reasons. The most portable choice once you leave AWS. (FastMCP still needs persistent
  client storage across restarts; on a non-AWS host use a local SQLite or Redis store instead of
  DynamoDB.)
- **Single user, just want to keep strangers out → Cloudflare Access service token** (your DNS is
  already at Cloudflare, so this is easy and needs no app code) **or a FastMCP static bearer token** (no
  external service at all).
- **Want full ownership and many users, no SaaS → self-hosted Keycloak/Authentik** (the most work).

**The honest take for a hobby tool:** full OAuth (Cognito/Auth0) earns its complexity only when several
distinct people each log in with their own identity. If it is just you, a **static bearer token** or
**Cloudflare Access** keeps the server private with far less setup. Start there, and add full OAuth later
if you ever open the tool to other users.

---

## 20. Sources for sections 16–19

Checked 2026-06-17. Prices change often (especially Hetzner's and Fly.io's) — re-check the official
pages before you commit money.

- WireGuard performance and lightweight kernel design (low CPU/RAM, high throughput vs OpenVPN):
  https://www.wireguard.com/performance/
- WireGuard real-world idle footprint (~40 MB RAM, <1% CPU with a dozen peers) and "1 vCPU / 1 GB is
  plenty" — third-party self-hosting guides: https://massivegrid.com/blog/wireguard-vpn-ubuntu-vps/ and
  https://webnestify.cloud/insights/cybersecurity-hardening/wireguard-easy-self-hosted-vpn/
- Tailscale (managed WireGuard coordination, free personal tier): https://tailscale.com/pricing/
- Hetzner price adjustment 15 June 2026 (official CX/CAX prices, excludes VAT):
  https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Hetzner Cloud line specs (CX/CAX vCPU/RAM/disk) and IPv4 surcharge (~€0.50/month):
  https://www.hetzner.com/cloud/ and https://costgoat.com/pricing/hetzner
- Hetzner June 2026 increase hitting CPX/CCX hardest (up to +176%): https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/
- Building an amd64 image when the project already builds arm64 (`docker buildx --platform linux/amd64,linux/arm64`; in CI the amd64 build is native), per §17.1: https://docs.docker.com/build/building/multi-platform/
- Fly.io pricing (`shared-cpu-1x` 256 MB ≈ $2.02/mo, 512 MB ≈ $3.32/mo, $0.02/GB EU/NA egress, volumes
  $0.15/GB/mo, TLS ≈ $0.10/mo, no new-account free tier): https://fly.io/docs/about/pricing/
- Fly.io scale-to-zero (`auto_stop_machines` / `auto_start_machines`): https://fly.io/docs/launch/autostop-autostart/
- Fly.io Tigris object storage (S3-compatible, integrated): https://fly.io/docs/tigris/
- FastMCP built-in auth providers (Cognito, Auth0, Google, GitHub, Azure, WorkOS, OIDC/JWT verifiers):
  https://gofastmcp.com/servers/auth/oauth-proxy and https://gofastmcp.com/servers/auth/oidc-proxy
- AWS Cognito free tier (10,000 MAU for direct/social sign-in): https://aws.amazon.com/cognito/pricing/
- Auth0 free tier (25,000 MAU since Sept 2024): https://auth0.com/pricing
- Cloudflare Access / Zero Trust pricing (free up to 50 users, then $7/user/month) and MCP service-token
  vs interactive-login behavior: https://www.cloudflare.com/plans/zero-trust-services/ and
  https://developers.cloudflare.com/cloudflare-one/access-controls/ai-controls/mcp-portals/

**Lower-confidence items to verify yourself before relying on them:**

- WireGuard footprint numbers are from third-party self-hosting reports, not measured for your box and
  device count. They are small either way; confirm with `free -m` and `top` once running.
- Hetzner add-on prices (backups +20%, snapshots ~€0.012/GB, volumes ~€0.048/GB, IPv4 €0.50) come from
  Hetzner's pricing pages and trackers; Hetzner re-prices often, so confirm live before ordering. All
  Hetzner prices exclude VAT.
- Fly.io dollar figures and the "no new-account free tier" status come from Fly's pricing page plus 2026
  third-party summaries; confirm on fly.io directly, as Fly adjusts pricing.
- MAU free-tier numbers (Cognito 10,000; Auth0 25,000; Cloudflare 50 users) are current as of the dates
  above but are exactly the kind of number providers change. Re-check before depending on them.
- FastMCP's exact `Auth0Provider` constructor and the non-AWS persistent `client_storage` options
  (SQLite/Redis) — confirm against the current FastMCP docs, the same caution as the deployment spec §7.3.

---

## 21. Dynamic Client Registration (DCR): what it means for Cognito and Auth0

This extends §19. You raised a real point: an MCP login is not plain OAuth. In early 2025 the MCP
specification expected the server side to support **Dynamic Client Registration (DCR, RFC 7591)**, and
most OAuth providers do not. Here is what that means today, for Cognito and Auth0, and how FastMCP
handles it.

### 21.1 Why MCP wanted DCR, and why the rule has since been relaxed

An MCP client (Claude Desktop and similar) connects to servers it has never seen before, and the
operator never registered that specific client in advance. Plain OAuth needs a client to be registered
first, to get a `client_id`. DCR was the answer: the client registers itself automatically at connect
time, with no manual setup.

The specification changed its position on DCR several times, always in one direction — from "you should
support it" toward "it is optional and being replaced":

| MCP spec revision | DCR requirement | Notes |
|---|---|---|
| 2025-03-26 | **SHOULD** support DCR | The MCP server was also treated as the OAuth server. |
| 2025-06-18 | SHOULD (now on the OAuth server + client, not the MCP server) | The MCP server became a pure "resource server" and **MUST** publish Protected Resource Metadata (RFC 9728) that points to a separate OAuth server. |
| 2025-11-25 (latest finalized) | **MAY** — kept only for backward compatibility | New preferred method: **Client ID Metadata Documents (CIMD)** — the client uses an HTTPS URL as its `client_id`, so no registration call is needed. |
| next revision (in draft as of mid-2026) | DCR **deprecated** | CIMD becomes the recommended method. |

**What this means for you:** the rule you remembered ("MCP needs DCR") was true in February 2025. It is
no longer a hard requirement. You do not have to track this closely, because **FastMCP handles whichever
method the client uses** (see 21.3). The MCP-specific rule that still holds is different: your server
must publish RFC 9728 Protected Resource Metadata pointing at your OAuth provider, and FastMCP's provider
classes do that for you.

### 21.2 Native DCR support: Cognito vs Auth0

This is where the two providers differ, if you were to use their DCR directly:

| | Native DCR support | Detail |
|---|---|---|
| **AWS Cognito** | **No** | Cognito user pools do not offer an RFC 7591 registration endpoint. To get real DCR on Cognito you would have to build it yourself (API Gateway + a Lambda that calls `CreateUserPoolClient` + DynamoDB to store the records), and Cognito limits how many app clients a user pool may have. Not worth doing. |
| **Auth0** | **Yes** | Auth0 has an open `POST /oidc/register` endpoint ("Dynamic Application Registration"). It is **turned off by default**. If you turn it on without protection, anyone on the internet can create applications in your tenant — Auth0 warns about this directly. Apps created this way are "third-party" and always show a consent screen. |

So Auth0 supports DCR and Cognito does not. **But with FastMCP you normally use neither provider's
native DCR** — the next part explains why.

### 21.3 How FastMCP handles it: the OAuth proxy

FastMCP solves the DCR question with a piece called **`OAuthProxy`**. It presents a DCR-compatible
interface to the MCP client (so the client can "register" and connect), but on the provider side it uses
**one app that you registered in advance**. Every MCP client maps to that single upstream app. The
client thinks it did dynamic registration; underneath, FastMCP used your fixed `client_id` and
`client_secret`.

The important result: **you do not need the provider to support DCR at all.** Both built-in providers are
built on this proxy:

- **`AWSCognitoProvider`** is built on `OAuthProxy`. The FastMCP docs state plainly that because Cognito
  does not support DCR, the integration uses the proxy. You register **one** Cognito app client, put its
  id and secret in env vars, and FastMCP does the rest.
- **`Auth0Provider`** is built on `OIDCProxy`, which sits on top of `OAuthProxy`. So even though Auth0
  *could* do native DCR, FastMCP's provider uses the same one-app approach. You register one Auth0 app,
  and you do **not** turn on Auth0's open DCR endpoint (and you should not, given the abuse risk).

What you write is small in both cases — roughly:

```python
AWSCognitoProvider(user_pool_id="eu-central-1_XXXXXXXX", aws_region="eu-central-1",
                   client_id="...", client_secret="...", base_url="https://mcp.ankify.dev")
# or
Auth0Provider(config_url="https://YOUR_TENANT/.well-known/openid-configuration",
              client_id="...", client_secret="...", audience="https://YOUR_API",
              base_url="https://mcp.ankify.dev")
```

The proxy also accepts the newer CIMD clients, so it covers both the old DCR style and the new one.

**The other path (only if you leave Cognito/Auth0).** If you ever pick a provider that *does* support
open, standards-based DCR — FastMCP names **WorkOS** and **Descope** — you can use `RemoteAuthProvider`
instead. Then FastMCP does not proxy at all: the MCP server is only a resource server, and each client
registers directly with that provider. You would choose this only with a DCR-native provider; for Cognito
and Auth0 the proxy is the correct and documented way.

### 21.4 The storage detail that matters in production

This sharpens the warning already in §19.5. The proxy must remember the client registrations and the
upstream tokens it created. By default FastMCP stores these **in memory on Linux**, which means **every
server restart loses them** and clients have to register again. It also derives its encryption key from
your upstream client secret, so rotating that secret invalidates the stored clients.

For a real deployment you must set two things together:

1. A fixed `jwt_signing_key` (so restarts and secret rotations do not invalidate clients).
2. A shared, persistent `client_storage` — the docs name **Redis or DynamoDB**, wrapped in encryption so
   tokens are not stored in plain text.

On AWS this is the DynamoDB table the deployment spec already mentions. Off AWS (Hetzner, Fly.io), use
**Redis or a local SQLite-backed store** instead. This is the same point §19.5 made, now with the reason:
without it, your MCP clients silently lose their registration whenever the server restarts.

### 21.5 Short answer

- The "MCP needs DCR" rule from February 2025 has been relaxed; DCR is now optional and is being replaced
  by CIMD. You do not need to act on this.
- **Cognito has no native DCR; Auth0 has it but off by default.** It does not matter, because **FastMCP's
  `OAuthProxy` presents DCR to the client and maps every client to one app you register in advance.** For
  both providers you register a single app and set `client_id` / `client_secret` in env — you never turn
  on the provider's own DCR.
- The one thing you must not skip is **persistent, shared client storage plus a fixed signing key**
  (DynamoDB on AWS; Redis or SQLite off AWS). Without it, clients re-register on every restart.

---

## 22. MCP authentication today: the accepted approach, and the simplest proper setup

This continues §21. You asked four things: if DCR is being deprecated, why deal with it at all; what the
accepted standard is now; how likely it is to change again within a few months; and the simplest way to
get a proper OAuth setup. You also said a database is available, so the storage point in §21.4 is not a
constraint — that is correct, and it keeps every proper option below open to you.

**Short answer:** you never write DCR yourself, so "deprecated" costs you nothing — FastMCP answers both
the old method (DCR) and the new one (CIMD) for you. The accepted standard is a small, stable shape: your
MCP server is only a *resource server*, it publishes one metadata file, and a separate identity provider
does the login. The spec will change again soon (the next revision is already dated 28 July 2026), but
only as small additions to that same shape. The simplest proper setup is to let a managed, MCP-aware
identity provider do the OAuth, wired in through one FastMCP class.

### 22.1 "Deprecated" does not mean "gone" — and you never implement DCR anyway

Two separate points answer "why bother?":

**First, "deprecated" in OAuth language means "do not build new things around it," not "removed."** A
deprecated method still works and is still accepted for backward compatibility. So even after the next
revision marks DCR deprecated, servers and clients keep supporting it. Real clients still rely on it in
mid-2026:

- The big hosted clients **added CIMD** between November 2025 and March 2026: VS Code, the Claude.ai
  connectors, ChatGPT, and Claude Code (from version 2.1.81). For these, CIMD is now the preferred path.
- But **not every client.** Cursor still does only DCR plus a manually pasted client id — no CIMD, with no
  announced date as of June 2026. The common `mcp-remote` bridge also cannot do CIMD yet. Older client
  versions are DCR-only too.

So a server that refused DCR would lose those users. The accepted answer is to **accept both** — and that
is exactly what you get without doing anything special.

**Second, and this is the real answer: you do not implement either method.** With FastMCP you do not write
a registration endpoint, and you do not choose DCR versus CIMD. The framework presents both to the client
and uses whichever the client speaks. CIMD handling is on by default. So "bother with DCR" is the wrong
frame — there is nothing for you to build or maintain for it. You pick a provider; the registration method
is handled by the framework, not by you.

### 22.2 The accepted standard (and why it is now stable)

The current accepted shape for securing a remote MCP server, agreed by the 2025-11-25 spec and by every
identity provider that supports MCP:

- **Your MCP server is an OAuth 2.1 *resource server* only.** It checks tokens. It does not run logins and
  does not issue tokens.
- It **publishes one metadata file**, Protected Resource Metadata (RFC 9728), at
  `/.well-known/oauth-protected-resource`. That file names your authorization server. This is the one
  MCP-specific requirement, and FastMCP serves it for you.
- A **separate authorization server (the identity provider)** does the login and issues tokens, with PKCE
  (the standard code-exchange protection) required.
- **Client registration:** CIMD preferred, DCR accepted as a fallback, a pre-registered client also
  allowed. As in 22.1, this is handled for you.
- **Each token is bound to your server** through RFC 8707: the client sends `resource=<your server URL>`,
  and your server checks the token was issued for it. This stops a token meant for another service being
  replayed against yours.

That is "proper OAuth" — standard OAuth 2.1, nothing custom. FastMCP's provider classes implement all of
it.

It helps to see how few revisions it took to reach this stable shape:

| MCP spec revision | What changed for auth |
|---|---|
| 2025-03-26 | First auth framework. The MCP server was treated as *both* the login server and the resource server — judged too heavy. |
| 2025-06-18 | The split that still holds: the server is a **resource server only**; **RFC 9728** metadata and **RFC 8707** token binding became required. |
| 2025-11-25 (latest finalized) | Added **CIMD** as the preferred registration method (SHOULD); dropped **DCR** to optional (MAY), kept for backward compatibility. |

The important line is the middle one. The architecture you build — resource server + RFC 9728 + external
provider + RFC 8707 — has not changed since June 2025. Only the client-registration detail moved, and that
detail is the part the framework handles for you.

### 22.3 Will it change again in three months? Yes — but not in a way that affects you

Be honest about this: the spec moves fast, and a change is already scheduled.

- The **next revision is dated 28 July 2026.** As of today it is a release candidate (its content was
  locked on 21 May 2026), so it ships in about six weeks.
- What it does is **add stricter checks**, not redesign anything: better defense against login-server
  mix-up attacks (RFC 9207 issuer validation), a field so desktop and command-line clients are typed
  correctly during registration, refresh-token guidance, and it moves DCR from "optional" to formally
  "deprecated" (still backward-compatible). It does **not** touch the resource-server model, RFC 9728,
  RFC 8707, or CIMD.
- **Pace:** revisions have come every three to eight months, and authorization is the most-edited area each
  time. So expect more small changes after July too.

Why this does not hurt you: because FastMCP (or a managed provider) implements these details, "the spec
changed" turns into "update the library" or "the provider already did it," not "rewrite your auth." The
core shape from 22.2 has been steady for a year, and the new edits are additions to it. **The way to stay
safe from the three-month-change problem is to not write your own OAuth** — let the library or the provider
handle each revision. Keep FastMCP reasonably current and you inherit the fixes.

### 22.4 The simplest proper setup, given a database is fine

You set two constraints: a database is available (so the persistent storage in §21.4 is not a blocker),
and it must be proper OAuth — no shortcuts such as a static API key or an "authless" server. Both paths
below are full OAuth 2.1. The difference is **who runs the login server.**

**Path A — let a managed, MCP-aware provider do the OAuth (least code, recommended).**
Your server stays a pure resource server: it only validates tokens and serves the RFC 9728 file. The
provider runs the login screen, the client registration (both DCR and CIMD), and token issuance. In
FastMCP this is one class:

```python
from fastmcp import FastMCP
from fastmcp.server.auth.providers.workos import AuthKitProvider

auth = AuthKitProvider(authkit_domain="https://your-project.authkit.app",
                       base_url="https://mcp.ankify.dev")
mcp = FastMCP(name="Ankify", auth=auth)
```

- Providers with a one-class FastMCP integration of this kind: **WorkOS AuthKit**, **Descope**,
  **Scalekit**, and WorkOS direct. **Auth0** also shipped first-class MCP support (generally available
  May 2026) and can act as this kind of provider.
- **Free tiers cover you many times over:** WorkOS AuthKit is free to 1,000,000 monthly users, Auth0 to
  25,000, Descope to 7,500; Scalekit is metered by tool calls.
- This path needs **no server-side token storage at all** — the provider issues the tokens — so the §21.4
  storage and signing-key setup does not apply here. You said a database is fine, so that point does not
  decide anything either way; it just means there is even less to run.
- It works on **any host** — AWS, Hetzner, or Fly — which fits the rest of this document if you move off
  AWS.

**Path B — keep the login server inside your own provider, through FastMCP's proxy (uses the database you
already have).**
Use `AWSCognitoProvider` (proxy) or `Auth0Provider` (OIDC proxy). You register one app in the provider;
FastMCP answers DCR and CIMD to clients against that one app and issues its own tokens. This is the §21.3
proxy approach. It needs the persistent shared `client_storage` and a fixed `jwt_signing_key` from §21.4 —
which you have said is fine (DynamoDB on AWS; Redis or SQLite off AWS). This is also proper OAuth. Choose
it if you specifically want the login server to stay inside your own AWS account, or you already use
Cognito for the app's users.

**Recommendation.** For the simplest, fully standard setup, use **Path A with a managed MCP-aware
provider** — **WorkOS AuthKit on the free tier** is the simplest to set up (one class, free at your scale,
runs on any host), with **Auth0's MCP support** as the alternative if you prefer Auth0. The strongest
reason is 22.3: the provider keeps up with the spec for you, which is your best protection against the next
revision. Pick **Path B** only if keeping the login server inside AWS matters more to you than having less
to maintain. Both are proper OAuth; you are only choosing who runs the authorization server.

### 22.5 Knowing which user a request is from, and your usage database

You still need your own database — for usage limits, quotas, and similar per-user data. Path A does not
change that and does not block it. The split is simple:

- **The identity provider owns *who the user is*.** After the user logs in, the provider issues an access
  token (a signed JWT). The MCP client then sends that token on every request, in the
  `Authorization: Bearer <token>` header.
- **Your database owns *what the user has done*** — usage counts, limits, plan. You key it by the user id
  that the token carries.

There is no "match the token to a user" step on your side. The token is a JWT that already contains a
stable user id in its **`sub`** ("subject") claim, signed by the provider. Your server checks the signature
against the provider's public keys, then reads the claim. The verified user id is inside the token.

In FastMCP, inside a tool:

```python
from fastmcp.server.dependencies import get_access_token

@mcp.tool
def convert_TSV_to_Anki_deck(...):
    token = get_access_token()        # the validated token for this request
    user_id = token.claims["sub"]     # stable, provider-issued user id -> your database key
    # read or increment usage in your own table, keyed by user_id
```

Points that matter:

- **`sub` is the right key** — it is unique and stable per provider. (`email` can change, so use it only for
  display. On Microsoft Entra the stable id is `oid`, not `sub`.)
- **It works the same in Path A and Path B.** Even though the proxy in Path B issues its own token, FastMCP
  hands your tool the verified upstream user, so `claims["sub"]` is the user id either way.
- **Tokens exist only over HTTP** (the AWS-hosted server). In local stdio mode there is no token and
  `get_access_token()` returns nothing — which is fine, since usage limits are for the hosted server.
- **FastMCP does not store your per-user data for you.** Its request context lives for one request only.
  Your usage limits live in your own database (DynamoDB on AWS), keyed by `sub` — the database you already
  planned.

So Path A keeps your database for application data only (usage limits), while the provider holds identity.
The difference from Path B is only what *else* the database holds: Path B also keeps OAuth state there (the
`client_storage` from §21.4); Path A does not, because the provider issues the tokens. Either way it is one
DynamoDB; Path A just keeps auth out of it.

### 22.6 Does Path A still fit on AWS Lambda? Yes — better than Path B

On Lambda, Path A is the **better** fit, not a worse one.

- **Path A is stateless.** Your Lambda only validates a JWT on each request (a signature check against the
  provider's public keys) and serves the small metadata file. There is no session to keep, no login
  callback to handle (login and callback happen at the provider, not on your Lambda), and no
  `client_storage`. That matches how Lambda works: short, independent invocations on containers that start
  and stop. AWS's own MCP-on-Lambda library states that only stateless MCP servers are a good fit.
- **Path B works on Lambda, but it is more work.** The proxy handles the login callback itself and issues
  its own tokens, so it needs the persistent shared `client_storage` and fixed `jwt_signing_key` from
  §21.4. On Lambda that storage must be DynamoDB (in-memory does not survive between invocations), which
  you have — so it is possible. But the multi-step login flow then runs across separate cold-started
  containers, each step reading DynamoDB, and you must manage the callback URL and redirect carefully. A
  signal: AWS's own end-to-end guide that uses the Cognito proxy pattern runs the server on **Fargate (a
  container), not Lambda.**

One point that is **not** about auth, but is the real Lambda question for this project: the MCP transport
must run in **stateless mode** on Lambda (set `stateless_http=True` and `json_response=True`), because
Lambda has no sticky sessions. And Lambda's request limits apply to your tool, not to auth: an HTTP API
Gateway has a **29-second** timeout and a **6 MB** response cap, and Python cannot stream on Lambda without
the Lambda Web Adapter. Your tool runs text-to-speech and builds an Anki deck, which can be slow and can
produce a large file — so for a big deck these limits, not the auth method, are what make Lambda awkward.
Returning a download link instead of the deck bytes, and keeping jobs short, helps; a persistent container
removes the limits, which is the trade-off the deployment spec weighs.

So: keep Path A on Lambda for the auth — it is the clean choice. Just know that the harder part of "MCP on
Lambda" is the tool's run time and response size, not the OAuth.

### 22.7 Short answer

- **"Deprecated" DCR is not removed.** It still works, and some clients (Cursor, the `mcp-remote` bridge,
  older versions) still need it — while the major hosted clients now prefer CIMD. You never write either
  one: FastMCP presents both and uses whichever the client speaks, with CIMD on by default. There is
  nothing for you to "bother" with.
- **The accepted standard** is a resource server that publishes RFC 9728 metadata, delegates login to an
  external provider, requires PKCE, and binds tokens with RFC 8707 — CIMD preferred, DCR as fallback.
  FastMCP implements all of it, and this shape has been stable since June 2025.
- **It will change again** (the next revision, 28 July 2026, is already a release candidate), but only as
  small additions to that shape. Let the library or the provider handle each change; do not write your own
  OAuth.
- **The simplest proper setup** is Path A: a managed MCP-aware provider through one FastMCP class — WorkOS
  AuthKit's free tier is the easiest, Auth0's MCP support the main alternative. Because your database is
  not a constraint, the Cognito or Auth0 proxy path (Path B, §21.3–21.4) is equally open if you would
  rather keep the login server inside AWS.
- **Tracking usage needs nothing special:** your own database (DynamoDB) holds the usage limits, keyed by
  the user id in the token's `sub` claim, which FastMCP gives you as `get_access_token().claims["sub"]`.
  The provider owns identity; your database owns usage. This works in both paths (22.5).
- **On AWS Lambda, Path A fits better than Path B** — a stateless token check, with no login callback or
  auth storage on the Lambda. The real Lambda constraint is your tool's run time and response size (the
  29-second timeout and 6 MB response cap), not the auth (22.6).

---

## 23. Will a personal WireGuard VPN work from Russia?

This extends §16. You asked two things: whether a personal exit VPN on Hetzner is allowed for you and a
few relatives, and whether it will actually work for connecting from inside Russia to blocked sites in
2026.

**Short answer:** the "is it allowed" answer is **yes**, with one condition about your billing address.
The "will it work from Russia" answer is: **not with plain WireGuard.** You need an obfuscated protocol,
and even then expect ongoing effort, because Russia now blocks in two separate ways — by protocol and by
hosting-provider address.

### 23.1 The extent of "personal" on Hetzner

A **closed** personal VPN — only you and a few named relatives have keys — is allowed. Hetzner's rules do
not mention VPNs at all; they forbid a short list of things (crypto mining, scanning other networks,
spoofed traffic), and a personal VPN is none of them. Hetzner even publishes a WireGuard setup guide and
a one-click WireGuard app.

The line is **not a user count.** It is about two things:

- **Openness.** A VPN open to strangers, or an exit node for the public (for example a Tor exit), draws
  abuse complaints and can get the account suspended. A handful of trusted relatives does not.
- **Abuse and traffic.** Everything your relatives do online comes from the box's one IP address. If a
  site sends a complaint, it comes to you, and Hetzner expects a fast reply (often within 24–48 hours).
  With a few trusted users this is rare.

**The one condition that is specific to Russia:** Hetzner stopped serving customers with a **Russian
billing address** (announced December 2023, effective January 2024). This is about the **account's
address, not where people connect from.** So your Hetzner account must be registered to a **non-Russian**
address. Your relatives connecting *to* the VPN from inside Russia is fine and is not a Hetzner problem.

### 23.2 How Russia blocks VPNs now: both protocol and provider address

You asked whether Russia blocks by VPN-provider IP or by detecting protocols. The 2025–2026 answer is
**both**, and this is the part that changed over the past year:

1. **Protocol detection (DPI).** Russia installed deep-packet-inspection equipment (called TSPU) at the
   ISPs. It recognizes the handshake of common VPN protocols — **plain WireGuard and OpenVPN are detected
   and blocked at connection time.** Reports through 2025 describe plain WireGuard going from "works" to
   "mostly broken" on these networks. An unobfuscated protocol fails regardless of which server it
   connects to.
2. **Provider / address reputation.** Since around mid-2025 Russia also degrades traffic to whole
   **datacenter address ranges** it treats as suspicious — including **Hetzner, OVH, DigitalOcean, AWS,
   Oracle, and Cloudflare.** The reported behavior is a connection that starts and then freezes after
   about 15–20 kilobytes, **even when the traffic looks like ordinary HTTPS.** Hetzner ranges have been
   specifically reported as affected.

So Russia blocks in two separate ways: one looks at **how you connect** (the protocol), the other at
**where you connect from** (the hosting provider's address range).

### 23.3 Why premium VPNs like RedShield still work

Your suspicion is correct: they use **non-standard, obfuscated protocols** that disguise VPN traffic as
ordinary web traffic, so the DPI cannot recognize it. The two strongest options used in Russia in 2026
are:

- **VLESS + XTLS Reality** (run with Xray). It imitates a real TLS handshake to a real public website,
  including that site's real certificate. To the DPI it looks like a normal HTTPS visit, and a probe that
  tries to test the server is sent to the real site instead. This is considered the most robust option.
- **AmneziaWG** — an obfuscated version of WireGuard. It keeps WireGuard's speed but removes the fixed
  signature the DPI looks for: it adds junk packets before the handshake, randomizes packet headers and
  sizes, and (in version 2.0) makes each server's pattern unique. It is easier to run than Reality, and
  good enough in most cases.

RedShield publicly supports both AmneziaWG and Xray VLESS Reality. (I could not read RedShield's own page
in full, so treat the exact list as likely but unconfirmed.) The general point is solid: the VPNs that
survive in Russia are the ones using obfuscation, not plain WireGuard or OpenVPN.

### 23.4 Does a small personal VPN help more than a big one? Partly

Your reasoning is half right, and the correction matters:

- **Right:** a personal server's IP address is **not on the public blocklists** of known commercial-VPN
  addresses (the lists that block NordVPN, ExpressVPN, and so on). So a personal VPN gets past that
  blocking, which a big commercial VPN cannot.
- **Missing piece:** Russia also scores the **hosting provider's whole address range**, and **Hetzner is
  on the suspicious list** (§23.2). An obscure personal IP inside a Hetzner range does **not** get past
  that, even with a perfect obfuscated protocol. This blocking is about the provider, not about whether
  your specific IP is well known.

So the combination with the best chance is **a personal/obscure server + an obfuscated protocol
(AmneziaWG or VLESS Reality).** That does beat a big commercial VPN on the address-blocklist problem. But
it does not remove the Hetzner-address-range risk, which obfuscation cannot fix. A datacenter IP from any
provider is also more likely to be slowed or shown CAPTCHAs by destination sites than a home internet IP
— and a home IP is not something a rented server can give you.

### 23.5 What to actually deploy, and how reliable it will be

If you want a personal censorship-resistant VPN on a rented box, used from inside Russia, in 2026:

- **Do not use plain WireGuard for this.** The §16 advice (plain WireGuard with `wg-easy`, or Tailscale)
  is right for a private tunnel to your own services, or for general privacy on untrusted Wi-Fi. It is the
  wrong tool for getting past Russian censorship.
- **Use an obfuscated protocol.** The easiest path is the **Amnezia** self-hosting app: it installs
  **AmneziaWG** (and can also install **VLESS Reality**) on a fresh server in about 15 minutes, with
  clients for phones and computers. Running both protocols gives you a fallback if one is blocked.
- **Reduce the Hetzner-address risk.** Because Hetzner ranges get degraded from Russia at times, keep a
  **second server on a different provider or region** as a backup, and be ready to recreate the server on
  a new IP if one gets slowed. Do not depend on a single Hetzner IP as the only route.
- **Account hygiene:** non-Russian billing address (§23.1), keep the VPN closed to just your relatives,
  and answer any abuse email quickly.

**Be honest about reliability.** This is a continuous process: Russia updates its blocking, the VPN tools
update to get around it, and this repeats. Expect it to work most of the time but to have times when it
does not — when Russia rolls out a new method, when a Hetzner range is degraded, or when a relative's
region has a temporary mobile-network shutdown. A paid provider like RedShield stays up by pushing new
settings within hours; as a self-hoster you do that maintenance yourself. The general direction in Russia
is more blocking, not less, so plan for ongoing maintenance rather than a one-time setup.

---

## 24. Sources for sections 21–23

Checked 2026-06-20. Specs, prices, and (especially) the Russia blocking situation change often. Re-check
the official pages before you rely on any of this.

**MCP authentication, DCR, and CIMD (§21–§22):**

- MCP authorization spec, 2025-06-18 (resource server model, RFC 9728 required, DCR SHOULD on the auth
  server + client): https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- MCP authorization spec, 2025-11-25 (DCR dropped to MAY/legacy; CIMD becomes the preferred method):
  https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- FastMCP OAuth Proxy (presents DCR to the client, uses one fixed upstream app; for providers without
  DCR): https://gofastmcp.com/servers/auth/oauth-proxy
- FastMCP AWS Cognito integration ("Cognito doesn't support DCR, so this uses the OAuth Proxy pattern";
  the one-app config): https://gofastmcp.com/integrations/aws-cognito
- FastMCP Auth0 integration (built on the OIDC proxy; register one app): https://gofastmcp.com/integrations/auth0
- FastMCP RemoteAuthProvider (the other path — for providers that DO support DCR, e.g. WorkOS, Descope):
  https://gofastmcp.com/servers/auth/remote-oauth
- Auth0 Dynamic Client Registration (open `/oidc/register`, off by default, third-party apps, abuse
  warning): https://auth0.com/docs/get-started/applications/dynamic-client-registration
- RFC 7591 (DCR) and RFC 9728 (Protected Resource Metadata):
  https://datatracker.ietf.org/doc/html/rfc7591 and https://datatracker.ietf.org/doc/html/rfc9728
- MCP authorization spec, next revision (release candidate dated 28 July 2026; additive hardening, DCR
  moved to formally deprecated): https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/
- CIMD proposal and the change that shipped it in the 2025-11-25 spec (SEP-991, "Client ID Metadata
  Documents"): https://github.com/modelcontextprotocol/modelcontextprotocol/issues/991
- MCP blog, client registration guidance (CIMD recommended for new servers, DCR kept for backward
  compatibility): https://blog.modelcontextprotocol.io/posts/client_registration/
- CIMD now shipping in clients: VS Code release notes (prefers CIMD over DCR):
  https://code.visualstudio.com/updates/v1_106 ; Claude.ai connector authentication (DCR, CIMD, and a
  pre-registered client all accepted): https://claude.com/docs/connectors/building/authentication ;
  ChatGPT Apps SDK authentication (CIMD preferred, DCR supported):
  https://developers.openai.com/apps-sdk/build/auth
- Clients that still need DCR: Cursor (DCR plus a manual client id, no CIMD as of June 2026):
  https://forum.cursor.com/t/mcp-oauth-cimd-support-plans-and-timelines/148096 ; the mcp-remote bridge
  cannot do CIMD yet: https://github.com/geelen/mcp-remote/issues/224
- FastMCP OAuth Proxy (answers both DCR and CIMD; CIMD on by default — the Path B proxy):
  https://gofastmcp.com/servers/auth/oauth-proxy
- FastMCP RemoteAuthProvider (pure resource server, for MCP-aware providers — the Path A approach):
  https://gofastmcp.com/servers/auth/remote-oauth
- FastMCP WorkOS AuthKit integration (the one-class Path A example):
  https://gofastmcp.com/integrations/authkit
- WorkOS AuthKit MCP docs (DCR + CIMD, RFC 9728, free tier): https://workos.com/docs/authkit/mcp
- Auth0 "Auth for MCP" generally available, May 2026:
  https://auth0.com/blog/auth0-auth-for-mcp-servers-generally-available/
- Descope CIMD support, generally available: https://www.descope.com/blog/post/cimd-support
- Scalekit MCP overview (DCR + CIMD; free tier metered by tool calls):
  https://docs.scalekit.com/guides/mcp/overview/

**User identity and AWS Lambda (§22.5–§22.6):**

- FastMCP — reading the validated token and its claims inside a tool (`get_access_token()`,
  `AccessToken.claims`, `TokenClaim`): https://gofastmcp.com/servers/dependency-injection and
  https://gofastmcp.com/servers/authorization
- FastMCP — the request context is per-request, not shared; store per-user data in your own database:
  https://gofastmcp.com/servers/context
- FastMCP HTTP deployment — stateless mode for serverless (`stateless_http=True`, `json_response=True`):
  https://gofastmcp.com/deployment/http
- AWS Labs — run MCP servers on AWS Lambda (stateless servers only):
  https://github.com/awslabs/run-model-context-protocol-servers-with-aws-lambda
- AWS — "Guidance for Deploying MCP Servers on AWS" (Cognito proxy + DynamoDB token store; note it runs on
  Fargate, a container, not Lambda):
  https://docs.aws.amazon.com/solutions/deploying-model-context-protocol-servers-on-aws/
- AWS Lambda response limits (6 MB buffered, 200 MB streamed; Python needs the Lambda Web Adapter to
  stream): https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html
- Amazon API Gateway 29-second integration timeout:
  https://aws.amazon.com/about-aws/whats-new/2024/06/amazon-api-gateway-integration-timeout-limit-29-seconds/

**Russia VPN (§23):**

- ACF/FBK "Access Denied" internet report, March 2026 (TSPU, protocol + datacenter-reputation blocking,
  "diversify away from easily scored subnets"): https://fbk.info/files/acf-internet-report-EN.pdf
- heise, "The 16-Kbyte trick" (datacenter-range degradation; Hetzner, OVH, DigitalOcean, AWS, Oracle,
  Cloudflare named): https://www.heise.de/en/news/The-16-Kbyte-trick-Russian-providers-block-foreign-content-again-10465087.html
- Tor Project forum, "Tor and Hetzner block in Russia" (Hetzner ranges specifically affected):
  https://forum.torproject.org/t/tor-and-hetzner-block-in-russia/16134
- Amnezia protocol notes (plain WireGuard "easily recognized by DPI… not recommended" for high-censorship
  countries): https://docs.amnezia.org/documentation/protocols-info/
- AmneziaWG docs (junk packets, header obfuscation, padding, v2.0 per-server signatures):
  https://docs.amnezia.org/documentation/amnezia-wg/
- Amnezia, "Amnezia on iOS in Russia" (AmneziaWG by default, VLESS Reality as the alternative):
  https://docs.amnezia.org/documentation/instructions/amnezia-on-ios-in-russia/
- Net4People BBS (ongoing community tracking of what works/breaks in Russia): https://github.com/net4people/bbs/issues/546
- zona.media, 2026 overview of Russian internet censorship (TSPU budget, AI filtering, trajectory):
  https://en.zona.media/article/2026/04/07/russian_internet_censorship_2026
- Hetzner WireGuard tutorial and one-click app (personal VPN is a supported use):
  https://docs.hetzner.com/cloud/apps/list/wireguard/

**Lower-confidence items to verify yourself before relying on them:**

- The **next MCP spec revision is dated 28 July 2026** and, as of today, is a release candidate (content
  locked 21 May 2026), not finalized. It is reported to move DCR to formally "deprecated" while keeping it
  for backward compatibility; the latest *finalized* spec is 2025-11-25, where DCR is still "MAY." Confirm
  the live spec before treating DCR as deprecated.
- **CIMD's underlying IETF document is still a draft** (`draft-ietf-oauth-client-id-metadata-document`),
  not yet a finished RFC. MCP's use of CIMD is finalized, but the base standard can still change.
- **Client support for CIMD is uneven.** The major hosted clients added it (late 2025 to early 2026), but
  Cursor and the `mcp-remote` bridge had not as of June 2026. Re-check current client support before you
  drop DCR.
- **FastMCP class names, the provider integrations, storage, and request APIs** (`OAuthProxy`, `OIDCProxy`,
  `AWSCognitoProvider`, `Auth0Provider`, `RemoteAuthProvider`, `AuthKitProvider`, `DescopeProvider`,
  `ScalekitProvider`, `jwt_signing_key`, `client_storage`, `enable_cimd`, `get_access_token`,
  `stateless_http`, `json_response`), and how a tool reads the user id (`get_access_token().claims["sub"]`)
  — the project runs FastMCP 3.2.4; confirm exact names and arguments against the current FastMCP docs, the
  same caution as §19 and the deployment spec §7.3. Some auth features landed after 3.2.4 (for example
  token-lifetime decoupling in 3.4), so check against your installed version.
- **AWS Lambda limits for MCP** (the 29-second API Gateway timeout, the 6 MB buffered response cap, and
  that Python needs the Lambda Web Adapter to stream) are current as of mid-2026, but this area changed
  over 2024–2026 (for example REST API response streaming). They affect the tool's run time and response
  size, not the OAuth. Confirm against the live AWS docs before you design around them.
- **Provider free-tier limits and MCP support** (WorkOS AuthKit, Auth0, Descope, Scalekit) come from the
  vendors' own docs and pricing pages read in mid-2026. Pricing and free-tier numbers change; confirm at
  signup.
- **RedShield's exact protocols** (AmneziaWG, Xray VLESS Reality) come from search results, not the
  provider's own page read in full. Likely correct, not confirmed.
- **Russia blocking specifics change month to month.** The datacenter-range degradation, which providers
  are hit "right now," and any single protocol's current status are reported by an advocacy-org report
  plus community and technical sources. Treat them as direction and risk, not as fixed facts; check
  Net4People BBS and Amnezia release notes for the current state before depending on a setup.
