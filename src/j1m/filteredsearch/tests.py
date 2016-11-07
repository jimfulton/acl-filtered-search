from pprint import pprint
import psycopg2
import unittest

from j1m.filteredsearch import filteredsearch
from j1m.filteredsearch import path_filteredsearch
from j1m.filteredsearch import upath_filteredsearch
from j1m.filteredsearch import array_filteredsearch

check_access = """
create or replace function check_access(
  acl Access[],
  principals varchar[],
  permission varchar)
  returns bool as $$
begin
  if acl is null then
    return null;
  end if;
  for i in 1 .. array_upper(acl, 1)
  loop
    if acl[i].who = any(principals) and
       (permission = any(acl[i].permissions) or
        '*' = any(acl[i].permissions))
    then
       return acl[i].allowed;
    end if;
  end loop;
  return null;
end
$$ language plpgsql;
"""

class Tests(unittest.TestCase):

    def setUp(self):
        conn = self.conn = psycopg2.connect('')
        cursor = self.cursor = conn.cursor()
        ex = self.ex = cursor.execute
        ex("create temp table docs (docid int)")
        ex("create temp table parents (docid int, parent_docid int)")
        ex("create temp table paths (docid int, path varchar)")
        ex("create temp table upaths (docid int, ancestor_docid int, ord int)")
        ex("""
        create temp table ace (
          docid int, allowed bool, who varchar, permission varchar, ord int
          )
        """)

        ex("""
        create type Access as (
          allowed bool, who varchar, permissions varchar[]);
        create temp table acl (docid int, acl Access[]);
        """)
        ex(check_access)

        def newdoc(docid, parent_docid):
            ex("insert into docs values(%s)", (docid,))
            ex("insert into parents values(%s, %s)", (docid, parent_docid))
            ex("insert into paths values(%s, %s)", (docid, path(docid)))
            for ord, ancestor_docid in enumerate(reversed(
                path(docid)[1:-1].split('/')
                )):
                ex("insert into upaths values(%s, %s, %s)",
                   (docid, ancestor_docid, ord))

        for i in range(1, 4):
            newdoc(i, 0)
            for j in range(1, 4):
                j += i*10
                newdoc(j, i)
                for k in range(1, 4):
                    k += j*10
                    newdoc(k, j)
                    for l in range(1, 4):
                        l += k*10
                        newdoc(l, k)
                        for m in range(1, 4):
                            m += l*10
                            newdoc(m, l)

        ex("""create temp table pace as
              select p.path || '%' as pathp,
                     a.allowed, a.who, a.permission, a.ord
              from paths p join ace a using (docid)
              """)

    def acl(self, docid, acl):
        aces = []
        acl = [(True, 'decoy', 'decoy')] + acl
        for order, (access, who, permissions) in enumerate(acl):
            if isinstance(permissions, str):
                permissions = permissions,

            for permission in permissions:
                self.ex("insert into ace values(%s, %s, %s, %s, %s)",
                        (docid, access, who, permission, order))
                self.ex("insert into pace values(%s, %s, %s, %s, %s)",
                        (path(docid) + '%', access, who, permission, order))

            permissions = ', '.join('"%s"' % p for p in permissions)
            aces.append("row(%s, '%s', '{%s}')" % (
                int(access), who, permissions))
        self.ex(
            "insert into acl values (%s, ARRAY[%s]::Access[])" % (
                docid, ', '.join(aces)))

    def search(self, permission, *principals):
        search = "select * from docs"
        results = filteredsearch(self.cursor, search, permission, principals)
        for f in (path_filteredsearch,
                  upath_filteredsearch,
                  array_filteredsearch,
                  ):
            self.assertEqual(f(self.cursor, search, permission, principals),
                             results)
        return results

    def tearDown(self):
        self.conn.close()

    def test_no_aces(self):
        self.assertEqual(self.search("read", "bob"), [])

    def test_basic(self):
        self.acl(111, [(True, "bob", "read")])
        self.acl(112, [(True, "sally", "edit")])

        expect = [(111,), (1111,), (1112,), (1113,), (11111,),
                  (11112,), (11113,), (11121,), (11122,), (11123,),
                  (11131,), (11132,), (11133,)]
        self.assertEqual(self.search("read", "bob"), expect)

    def test_true_before_false(self):
        self.acl(111, [(True, "bob", "read"), (False, "bob", "read")])
        expect = [(111,), (1111,), (1112,), (1113,), (11111,),
                  (11112,), (11113,), (11121,), (11122,), (11123,),
                  (11131,), (11132,), (11133,)]
        self.assertEqual(self.search("read", "bob"), expect)

    def test_false_before_true(self):
        self.acl(111, [(False, "bob", "read"), (True, "bob", "read")])
        self.acl(11,  [(False, "bob", "read"), (True, "bob", "read")])
        self.assertEqual(self.search("read", "bob"), [])

    def test_no_acquire(self):
        self.acl(11, [(True, "bob", "read"), (False, "bob", "read")])
        self.acl(111, [(False, "bob", "read"), (True, "bob", "read")])
        expect = [(11,), (112,), (113,), (1121,), (1122,), (1123,),
                  (1131,), (1132,), (1133,), (11211,), (11212,),
                  (11213,), (11221,), (11222,), (11223,), (11231,),
                  (11232,), (11233,), (11311,), (11312,), (11313,),
                  (11321,), (11322,), (11323,), (11331,), (11332,),
                  (11333,)]
        self.assertEqual(self.search("read", "bob"), expect)

    def test_extra_noise(self):
        self.acl(11, [(True, "bob", "read"),
                      (True, "all", "read"),
                      (True, "sally", "read"),
                      (False, "bob", "read")])
        self.acl(111, [(False, "bob", "read"), (True, "bob", "read")])
        expect = [(11,), (112,), (113,), (1121,), (1122,), (1123,),
                  (1131,), (1132,), (1133,), (11211,), (11212,),
                  (11213,), (11221,), (11222,), (11223,), (11231,),
                  (11232,), (11233,), (11311,), (11312,), (11313,),
                  (11321,), (11322,), (11323,), (11331,), (11332,),
                  (11333,)]
        self.assertEqual(self.search("read", "bob", "all"), expect)

    def test_all_permissions(self):
        self.acl(111, [(True, "bob", "*")])
        expect = [(111,), (1111,), (1112,), (1113,), (11111,),
                  (11112,), (11113,), (11121,), (11122,),
                  (11123,), (11131,), (11132,), (11133,)]
        self.assertEqual(self.search("read", "bob"), expect)


def path(docid):
    if docid:
        return path(docid // 10) + (str(docid) + '/')
    else:
        return '/'

def test_suite():
    return unittest.makeSuite(Tests)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

