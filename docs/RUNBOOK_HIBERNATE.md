# Postways – Hibernate & Restore Runbook

> **Lightsail · Snapshot · Cloudflare · S3**

How to **completely stop paying** for the production instance when the app is
not needed, and how to **bring it back** later from a snapshot.

Follow it literally. Every command runs from your **local machine** using the
AWS CLI unless marked **[on server]**.

---

## Why this works

Lightsail bills a flat monthly rate for an instance **whether it is running or
stopped** — the "Stop" button does **not** save money. The only way to stop
paying is to **delete** the instance. We snapshot it first so it can be
recreated exactly as it was.

| State | Monthly cost |
|-------|-------------|
| Instance running (`small_3_0`) | ~$12.00 |
| Instance stopped | ~$12.00 (no savings) |
| **Hibernated** (deleted + snapshot kept, IP released) | **~$0.70** |
| S3 bucket `media.postways.net` (~35 MB) | ~$0.001 (unchanged either way) |

**S3 is independent** — it is never touched by this procedure. All post images
and thumbnails survive hibernation untouched and reconnect automatically on
restore.

---

## 0. Environment Overview

| Item | Value |
|------|-------|
| AWS CLI profile | `default` (admin — the `postways-v2-app` profile is S3-only and cannot manage Lightsail) |
| Region | `eu-central-1` |
| Availability zone | `eu-central-1a` *(verify — see below)* |
| Instance name | `postways-v2-lightsail` |
| Bundle (plan) | `small_3_0` (2 GB / 2 vCPU / 60 GB) |
| Static IP name | `postways-v2-aws-lightsail-static-ip` |
| S3 bucket | `media.postways.net` (not affected) |
| Project dir **[on server]** | `/srv/postways-v2` |
| Compose file **[on server]** | `docker/docker-compose.prod.yml` |
| DNS | Cloudflare A record → instance public IP |

> **Confirm the AZ before you start** (needed for restore):
> ```bash
> aws lightsail get-instances --profile default \
>   --query 'instances[?name==`postways-v2-lightsail`].location.availabilityZone' --output text
> ```

---

## Prerequisites

- AWS CLI v2 configured with the `default` (admin) profile.
- Access to the **Cloudflare dashboard** to edit the DNS A record.
- SSH access to the instance (`ubuntu@<public-ip>`).

---

## PART A — Hibernate (stop all charges)

### A1. (Optional but recommended) Take a logical DB backup

The snapshot already captures the whole disk **including the Postgres data
volume**, so this is belt-and-suspenders. Skip if you trust the snapshot.

```bash
# [on server]
cd /srv/postways-v2
docker compose -f docker/docker-compose.prod.yml exec -T db \
  pg_dump -U postgres postways > ~/postways-pre-hibernate-$(date +%F).sql
# then copy it somewhere safe, e.g. S3:
aws s3 cp ~/postways-pre-hibernate-*.sql s3://media.postways.net/backups/ --profile default
```

### A2. Gracefully stop the app

```bash
# [on server]
cd /srv/postways-v2
docker compose -f docker/docker-compose.prod.yml down
```

### A3. Create the instance snapshot

```bash
P=default
SNAP=postways-v2-snap-$(date +%Y-%m-%d)

aws lightsail create-instance-snapshot --profile $P \
  --instance-name postways-v2-lightsail \
  --instance-snapshot-name $SNAP

echo "Snapshot name: $SNAP   # <-- write this down; you need it to restore"
```

### A4. Wait until the snapshot is `available`

**Do not delete anything until this prints `available`** (takes several minutes).

```bash
aws lightsail get-instance-snapshot --profile default \
  --instance-snapshot-name "$SNAP" \
  --query 'instanceSnapshot.{state:state,sizeGb:sizeInGb,fromBundle:fromBundleId}' \
  --output table
```

### A5. Delete the instance (this is what stops the ~$12/mo)

```bash
aws lightsail delete-instance --profile default \
  --instance-name postways-v2-lightsail
```

### A6. Release the static IP (avoids ~$3.60/mo idle charge)

A static IP is free **only while attached** to an instance. Detached, it bills
hourly — so release it. You will get a new IP on restore and update one
Cloudflare record.

```bash
aws lightsail release-static-ip --profile default \
  --static-ip-name postways-v2-aws-lightsail-static-ip
```

> **Want to keep the same IP instead?** Skip A6. You then keep paying ~$3.60/mo
> while hibernated (total ~$4.30/mo) but avoid the DNS change on restore.

### A7. Verify everything is gone

```bash
aws lightsail get-instances  --profile default --query 'instances[].name'
aws lightsail get-static-ips --profile default --query 'staticIps[].name'
aws lightsail get-instance-snapshots --profile default \
  --query 'instanceSnapshots[].{name:name,state:state}' --output table
```

Expect: **no instance**, **no static IP**, and **one snapshot** in `available`
state. ✅ You are now paying ~$0.70/mo (snapshot storage only).

---

## PART B — Restore (bring the app back)

### B1. Recreate the instance from the snapshot

> **Bundle must be the same size or larger** than the snapshot. You **cannot**
> shrink to a smaller plan this way (e.g. `micro_3_0`) — that needs a manual
> migration.

```bash
P=default
SNAP=postways-v2-snap-YYYY-MM-DD   # <-- the snapshot name from step A3

aws lightsail create-instances-from-snapshot --profile $P \
  --instance-snapshot-name "$SNAP" \
  --instance-names postways-v2-lightsail \
  --availability-zone eu-central-1a \
  --bundle-id small_3_0
```

### B2. Wait until the instance is `running`

```bash
aws lightsail get-instance --profile default \
  --instance-name postways-v2-lightsail \
  --query 'instance.state.name' --output text
```

### B3. Allocate and attach a static IP

```bash
aws lightsail allocate-static-ip --profile default \
  --static-ip-name postways-v2-aws-lightsail-static-ip

aws lightsail attach-static-ip --profile default \
  --static-ip-name postways-v2-aws-lightsail-static-ip \
  --instance-name postways-v2-lightsail

# Note the new public IP:
aws lightsail get-static-ip --profile default \
  --static-ip-name postways-v2-aws-lightsail-static-ip \
  --query 'staticIp.ipAddress' --output text
```

### B4. Open the firewall ports

Restoring from a snapshot can reset the instance firewall to blueprint
defaults. Ensure SSH/HTTP/HTTPS are open.

```bash
aws lightsail put-instance-public-ports --profile default \
  --instance-name postways-v2-lightsail \
  --port-infos \
    fromPort=22,toPort=22,protocol=TCP \
    fromPort=80,toPort=80,protocol=TCP \
    fromPort=443,toPort=443,protocol=TCP
```

### B5. Update Cloudflare DNS

In the Cloudflare dashboard, edit the **A record** for the domain to point to
the **new IP** from step B3. (Skip if you kept the old IP — see note in A6.)

### B6. Start the app

```bash
# [on server]  -- ssh ubuntu@<new-ip>
cd /srv/postways-v2
docker compose -f docker/docker-compose.prod.yml up -d
docker compose -f docker/docker-compose.prod.yml ps
```

### B7. Verify

- [ ] All containers `Up` (`web`, `nginx`, `db`, `redis`, `celery_worker`, `celery_beat`).
- [ ] Site loads over HTTPS via the domain.
- [ ] Post images load (confirms S3 connection intact).
- [ ] Likes update in real time (confirms WebSocket/Redis).
- [ ] DNS resolves to the new IP: `dig +short <your-domain>`

> The app reconnects to S3 automatically — the bucket name and IAM credentials
> live in the server's `config/.env`, which is inside the snapshot. No S3
> reconfiguration is needed.

### B8. (Optional) Clean up the snapshot

Keep it if you plan to hibernate again. To stop the ~$0.70/mo once you're
satisfied the restore is healthy:

```bash
aws lightsail delete-instance-snapshot --profile default \
  --instance-snapshot-name "$SNAP"
```

---

## Rollback / Troubleshooting

| Symptom | Action |
|---------|--------|
| Site unreachable after restore | Re-check B4 (ports) and B5 (DNS → new IP). |
| 502 from nginx | `docker compose ... ps`; check `web` is up; review logs. |
| Images 403/404 | Confirm `config/.env` has `AWS_STORAGE_BUCKET_NAME=media.postways.net` and valid `postways-v2-app` keys. |
| DB looks empty | Restore the dump from A1: `cat dump.sql \| docker compose ... exec -T db psql -U postgres postways`. |
| Need same IP, already released it | IPs are not reservable after release; update Cloudflare to the new IP. |

---

## Cost Summary

| Phase | Monthly cost |
|-------|-------------|
| Running | ~$12.00 + ~$0.001 S3 |
| Hibernated (IP released) | **~$0.70** (snapshot only) |
| Hibernated (IP kept) | ~$4.30 |
