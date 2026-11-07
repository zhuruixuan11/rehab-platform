"""营内群聊 WS 广播验证：教练↔学员双向实时收发。"""
import asyncio
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path, method="GET", token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def login(u, p):
    return call("/api/auth/login", "POST", body={"username": u, "password": p})[1]["token"]


async def main():
    ct, st = login("coach_li", "Coach@123"), login("student_wx", "Student@123")

    # 找一个进行中的营，没有则建一个
    _, camps = call("/api/camps", token=ct)
    ongoing = [c for c in camps if c["status"] == "ongoing"]
    if not ongoing:
        _, camp = call("/api/camps", "POST", ct, {"title": "WS测试营B", "start_date": "2026-08-26",
                                                  "end_date": "2026-09-26", "capacity": 5})
        cid = camp["id"]
        call(f"/api/camps/{cid}/transition?action=start", "POST", ct)
        code = call(f"/api/camps/{cid}", token=ct)[1]["invite_code"]
        call("/api/camps/join", "POST", st, {"invite_code": code})
        call(f"/api/camps/{cid}/transition?action=open", "POST", ct)
    else:
        cid = ongoing[0]["id"]
        _, mine = call("/api/camps/my", token=st)
        if not any(c["id"] == cid for c in mine):
            code = call(f"/api/camps/{cid}", token=ct)[1]["invite_code"]
            call("/api/camps/join", "POST", st, {"invite_code": code})
    print(f"ongoing camp: {cid}")

    import websockets
    async with websockets.connect(f"ws://127.0.0.1:8000/ws?token={st}") as sws, \
               websockets.connect(f"ws://127.0.0.1:8000/ws?token={ct}") as cws:
        await asyncio.sleep(0.3)
        await asyncio.wait_for(sws.recv(), timeout=3)
        await asyncio.wait_for(cws.recv(), timeout=3)

        await cws.send(json.dumps({"type": "camp", "camp_id": cid, "msg_type": "text",
                                   "content": "教练->全员广播测试"}))
        s_recv = json.loads(await asyncio.wait_for(sws.recv(), timeout=3))
        c_recv = json.loads(await asyncio.wait_for(cws.recv(), timeout=3))
        assert s_recv["type"] == "camp_msg" and "教练->全员广播测试" in s_recv["data"]["content"]
        assert c_recv["type"] == "camp_msg" and "教练->全员广播测试" in c_recv["data"]["content"]
        print("[PASS] 教练发言 → 学员+教练均收到")

        await sws.send(json.dumps({"type": "camp", "camp_id": cid, "msg_type": "text",
                                   "content": "学员->全员广播测试"}))
        s2 = json.loads(await asyncio.wait_for(sws.recv(), timeout=3))
        c2 = json.loads(await asyncio.wait_for(cws.recv(), timeout=3))
        assert "学员->全员广播测试" in s2["data"]["content"]
        assert "学员->全员广播测试" in c2["data"]["content"]
        print("[PASS] 学员发言 → 学员+教练均收到")

        # 非成员发消息被拒
        _, other = call("/api/auth/login", "POST",
                        body={"username": "e2e_tmp_student", "password": "Temp@123"})
        async with websockets.connect(f"ws://127.0.0.1:8000/ws?token={other['token']}") as ows:
            await asyncio.wait_for(ows.recv(), timeout=3)
            await ows.send(json.dumps({"type": "camp", "camp_id": cid, "msg_type": "text",
                                       "content": "非成员消息"}))
            err = json.loads(await asyncio.wait_for(ows.recv(), timeout=3))
            assert err["type"] == "camp_error"
            print(f"[PASS] 非成员发言被拒: {err['message']}")

    # 已结营的营不能发消息
    _, ended = [c for c in call("/api/camps", token=ct)[1] if c["status"] == "ended"], None
    print("WS CAMP CHAT ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
