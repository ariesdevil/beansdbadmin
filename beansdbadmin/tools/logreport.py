#!/usr/bin/env python
# encoding: utf-8

import sqlite3
import logging
import getpass
import json
import os
from pprint import pprint
from beansdbadmin.core.zookeeper import ZK
from beansdbadmin.core.zkcli import get_servers
from beansdbadmin.core.server_info import get_http

logger = logging.getLogger('logerr')
LOG_FORMAT = '%(asctime)s-%(name)s-%(levelname)s-%(message)s'

if getpass.getuser() in ("beansdb", "root"):
    SQLITE_DB_PATH = '/data/beansdbadmin/log_err.db'
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)
else:
    SQLITE_DB_PATH = './log_err.db'
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)


def send_sms(msg):
    # should be implemented by yourself
    logging.warn("send sms: %s", msg)
    return


class LOGERR(object):
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.cursor = self.conn.cursor()

    def create_table(self):
        self.cursor.execute("""CREATE TABLE log_err (
            id INTEGER PRIMARY KEY,
            server TEXT,
            ts TEXT,
            level,
            fname,
            lineno,
            msg
           )""")
        self.conn.commit()

    def close(self):
        self.conn.close()

    def add(self, server, ts, level, fname, lineno, msg):
        self.cursor.execute(
            """INSERT INTO log_err (server, ts, level, fname, lineno, msg)
           VALUES (:server, :ts, :level, :fname, :lineno, :msg)
        """, {'server': server,
              'ts': ts,
              'level': level,
              'fname': fname,
              'lineno': lineno,
              'msg': msg})
        self.conn.commit()

    def get(self, server, ts):
        self.cursor.execute("""select * from log_err
           WHERE server = :server and ts = :ts
        """, {'server': server,
              'ts': ts})
        return self.cursor.fetchall()

    def get_all(self):
        self.cursor.execute("SELECT * FROM log_err")
        return self.cursor.fetchall()


def report_err(db, server, err):
    ts = err['TS'][:19]
    old = db.get(server, ts)
    if old:
        logging.debug("%s %s exist", server, ts)
    else:
        db.add(server, ts, err["Level"], err["File"], err["Line"], err["Msg"])
        logging.warn("%s %s added", server, ts)
        send_sms(
            "%s %s %s %s %s" %
            (server, err["Level"], err["File"], err["Line"], err["Msg"][:100]))


def check_errs(db, server):
    logs = json.loads(get_http(server, "loglast"))
    errs = logs[2], logs[3]
    for e in errs:
        if e is not None:
            report_err(db, server, e)


def report_fail(server, e):
    logging.error("%s fail: %s", server, e)
    send_sms("%s %s" % (server, e))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i',
                        '--init',
                        action='store_true',
                        help="Init database.")
    parser.add_argument('-q',
                        '--query',
                        action='store_true',
                        help="Query the running buckets.")
    parser.add_argument('-c',
                        '--cluster',
                        required=True,
                        choices=['db256', 'fs', 'test'],
                        help='zk')
    args = parser.parse_args()

    db = LOGERR(SQLITE_DB_PATH)
    if args.init:
        db.create_table()
        return

    if args.query:
        pprint(db.get_all())
        return

    servers = get_servers(ZK(args.cluster))
    for s in servers:
        try:
            check_errs(db, s)
        except Exception as e:
            report_fail(s, e)


if __name__ == '__main__':
    main()
