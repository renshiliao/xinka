#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xinka 留言板管理端（SSH 用·我后台看/审）
用法:
  python3 admin.py stats              # 总账（各状态计数）
  python3 admin.py list               # 待审清单（pending）
  python3 admin.py all                # 全部留言
  python3 admin.py approve <ID>       # 通过→上墙
  python3 admin.py reject <ID>        # 拒绝→删除
"""
import sys
import time
import sqlite3

DB = "/opt/data/xinka_guestbook/guestbook.db"


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def show(rows, title):
    print(f"\n=== {title}（{len(rows)} 条）===")
    for r in rows:
        t = time.strftime("%m-%d %H:%M", time.localtime(r["created"]))
        print(f'#{r["id"]} [{t}] {r["name"]} ({r["ip"]}) → {r["status"]}')
        print(f'   内容：{r["content"][:120]}')
        if r["contact"]:
            print(f'   联系：{r["contact"]}')


def main():
    c = db()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        for s in ("pending", "approved", "all"):
            if s == "all":
                n = c.execute("SELECT COUNT(*) FROM msgs").fetchone()[0]
            else:
                n = c.execute(
                    "SELECT COUNT(*) FROM msgs WHERE status=?", (s,)
                ).fetchone()[0]
            print(f"{s:10s}: {n}")
    elif cmd == "list":
        show(c.execute(
            "SELECT * FROM msgs WHERE status='pending' ORDER BY created"
        ).fetchall(), "待审清单")
    elif cmd == "all":
        show(c.execute(
            "SELECT * FROM msgs ORDER BY created DESC LIMIT 30"
        ).fetchall(), "全部留言")
    elif cmd in ("approve", "reject") and len(sys.argv) > 2:
        mid = int(sys.argv[2])
        if cmd == "approve":
            c.execute(
                "UPDATE msgs SET status='approved', reviewed=? WHERE id=?",
                (time.time(), mid))
            print(f"✅ #{mid} 已通过·上墙")
        else:
            c.execute("DELETE FROM msgs WHERE id=?", (mid,))
            print(f"🗑️ #{mid} 已拒绝删除")
        c.commit()
    else:
        print(__doc__)
    c.close()


if __name__ == "__main__":
    main()
