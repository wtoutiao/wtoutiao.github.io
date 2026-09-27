import json, base64, os, urllib.request

TOKEN = os.environ["GH_TOKEN"]
REPO = "wtoutiao/wtoutiao.github.io"
BRANCH = "main"
API = "https://api.github.com"
SITE = r"C:\Users\Mr.wang\Doubao\chats\2026-09-27\new-chat\site_demo"

# 强制使用正确IP
# 140.82.112.6 works. Use Host header override.

def api(method, path, data=None):
    url = API + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "token " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "doubao-agent")
    req.add_header("Content-Type", "application/json")
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    # 强制走正确IP: 用底层socket替换
    import socket
    orig_getaddrinfo = socket.getaddrinfo
    def fixed_getaddrinfo(*args, **kwargs):
        if args and args[0] == "api.github.com":
            # 返回 (family, type, proto, canonname, sockaddr) 用正确IP
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.6", 443))]
        return orig_getaddrinfo(*args, **kwargs)
    socket.getaddrinfo = fixed_getaddrinfo
    try:
        with urllib.request.urlopen(req, data=body, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        print("HTTP ERROR", e.code, raw[:500])
        return e.code, None

# 1) 获取当前分支最新 commit sha
status, ref = api("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH))
print("ref:", status, ref.get("object", {}).get("sha") if ref else None)
base_sha = ref["object"]["sha"]

# 2) 收集站点文件
files = []
for root, dirs, fnames in os.walk(SITE):
    for fn in fnames:
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, SITE).replace("\\", "/")
        with open(full, "rb") as f:
            content = f.read()
        files.append({"path": rel, "content": content})

print("files to push:", [f["path"] for f in files])

# 3) 创建 blobs
blob_shas = {}
for f in files:
    status, blob = api("POST", "/repos/%s/git/blobs" % REPO, {
        "content": base64.b64encode(f["content"]).decode("ascii"),
        "encoding": "base64"
    })
    if status != 201:
        raise SystemExit("blob failed for " + f["path"])
    blob_shas[f["path"]] = blob["sha"]
print("blobs created:", len(blob_shas))

# 4) 创建 tree
tree_entries = [{"path": p, "mode": "100644", "type": "blob", "sha": s} for p, s in blob_shas.items()]
status, tree = api("POST", "/repos/%s/git/trees" % REPO, {
    "base_tree": base_sha,
    "tree": tree_entries
})
print("tree:", status)
tree_sha = tree["sha"]

# 5) 创建 commit
status, commit = api("POST", "/repos/%s/git/commits" % REPO, {
    "message": "Initial site: BackyardGardenHub",
    "tree": tree_sha,
    "parents": [base_sha]
})
print("commit:", status, commit.get("sha") if commit else None)
commit_sha = commit["sha"]

# 6) 更新 ref
status, upd = api("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH), {
    "sha": commit_sha,
    "force": True
})
print("update ref:", status, upd.get("object", {}).get("sha") if upd else None)
print("DONE")
