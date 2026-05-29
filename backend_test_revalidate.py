"""
Re-validate Build #22 backend tests C11 (daily check-in status preview after claim)
and J33 (/system/network corrected thresholds).
"""
import json
import time
import uuid
import requests

BASE = "https://ios-clone-platform.preview.emergentagent.com/api"


def section(t):
    print(f"\n{'='*60}\n{t}\n{'='*60}")


def main():
    results = []

    # ====== C11 ======
    section("C11 — Daily check-in status preview after claim")

    email = f"scminer.qa.{uuid.uuid4().hex[:10]}@gmail.com"
    pw = "QaTestPwd!9z"

    r = requests.post(f"{BASE}/auth/register", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  registered {email}")

    # Initial status
    r = requests.get(f"{BASE}/daily-checkin/status", headers=headers, timeout=30)
    assert r.status_code == 200, f"status pre: {r.status_code} {r.text}"
    pre = r.json()
    print(f"  status BEFORE claim: available={pre.get('available')} next_step={pre.get('next_step')} next_reward_ghs={pre.get('next_reward_ghs')}")
    assert pre["available"] is True
    assert pre["next_step"] == 1
    assert pre["next_reward_ghs"] == 1.2

    # Claim
    r = requests.post(f"{BASE}/daily-checkin", headers=headers, timeout=30)
    assert r.status_code == 200, f"claim failed: {r.status_code} {r.text}"
    claim = r.json()
    print(f"  claim result: streak={claim.get('streak')} awarded_usd={claim.get('awarded_usd')} reward_ghs={claim.get('reward_ghs')}")
    assert claim["streak"] == 1

    # Status after claim — THIS IS THE FIX VERIFICATION
    r = requests.get(f"{BASE}/daily-checkin/status", headers=headers, timeout=30)
    assert r.status_code == 200, f"status post: {r.status_code} {r.text}"
    post = r.json()
    print(f"  status AFTER claim: available={post.get('available')} next_step={post.get('next_step')} next_reward_ghs={post.get('next_reward_ghs')} streak={post.get('streak')}")

    c11_pass = (
        post.get("available") is False
        and post.get("next_step") == 2
        and post.get("next_reward_ghs") == 1.6
        and post.get("streak") == 1
    )
    if c11_pass:
        print("  ✅ C11 PASS")
        results.append(("C11", True, ""))
    else:
        msg = f"available={post.get('available')} next_step={post.get('next_step')} next_reward_ghs={post.get('next_reward_ghs')} streak={post.get('streak')}"
        print(f"  ❌ C11 FAIL — {msg}")
        results.append(("C11", False, msg))

    # ====== J33 ======
    section("J33 — /system/network hashrate (corrected threshold)")
    r = requests.get(f"{BASE}/system/network", timeout=30)
    assert r.status_code == 200, f"system/network: {r.status_code} {r.text}"
    n = r.json()
    print(f"  payload: {json.dumps(n, indent=2)}")
    nh = n.get("network_hashrate_ghs")
    rew = n.get("daily_block_rewards_btc")
    print(f"  network_hashrate_ghs={nh}  daily_block_rewards_btc={rew}")
    j33_pass = (
        isinstance(nh, (int, float)) and nh > 1e9
        and isinstance(rew, (int, float)) and rew > 100
    )
    if j33_pass:
        print("  ✅ J33 PASS")
        results.append(("J33", True, ""))
    else:
        msg = f"network_hashrate_ghs={nh} daily_block_rewards_btc={rew}"
        print(f"  ❌ J33 FAIL — {msg}")
        results.append(("J33", False, msg))

    # Summary
    section("SUMMARY")
    passes = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, msg in results:
        print(f"  {'✅' if ok else '❌'} {name} {msg}")
    print(f"\n  RESULT: {passes}/{total} PASS")
    return passes == total


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
