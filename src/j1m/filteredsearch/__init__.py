
template = """
with recursive
     text_results as (%(search)s),
     allowed(docid, id, parent_docid, allowed %(extra)s) as (
       select docid, id, parent_docid, allowed %(extra)s from (
         select distinct on (r.docid)
                r.docid, r.docid as id, p.parent_docid, a.allowed %(extra)s
         from text_results r
         join parents p using (docid)
         left join ace a on (
           a.docid = r.docid and
           a.permission in ('%(permission)s', '*') and
           a.who in %(principals)s
           )
         order by r.docid, a.ord
         ) base
     union all
       select docid, id, parent_docid, allowed %(extra)s from (
         select distinct on (p.docid)
                p.docid, p.id, p.parent_docid, a.allowed %(extra)s
         from (select allowed.docid, p.docid as id, p.parent_docid %(extra)s
               from allowed, parents p
               where allowed.allowed is null and
                     allowed.parent_docid = p.docid) p
              left join ace a on (
                a.docid = p.id and
                a.permission in ('%(permission)s', '*') and
                a.who in %(principals)s
                )
         order by p.docid, a.ord
         ) recursive
     )
select docid %(extra)s from allowed where allowed

"""

def filteredsearch(cursor, search, permission, principals, extra='',
                   template=template):
    principals = repr(principals).replace(',)', ')')
    sql = template % dict(
        search=search, permission=permission, principals=principals,
        extra=extra and ", " + extra)
    if cursor is None:
        print(sql)
    else:
        try:
            cursor.execute(sql)
        except Exception:
            print(sql)
            raise
        return cursor.fetchall()

path_template = """
select docid %(extra)s from (
  select distinct on (docid) s.*, a.allowed
  from
    (%(search)s) s
  join paths p using (docid)
  join pace a on (
    p.path like a.pathp and
    a.permission in ('%(permission)s', '*') and
    a.who in %(principals)s
    )
  order by s.docid, a.pathp desc, a.ord
) _
where allowed
"""

def path_filteredsearch(cursor, search, permission, principals, extra=''):
    return filteredsearch(cursor, search, permission, principals, extra,
                          template=path_template)

upath_template = """
select docid %(extra)s from (
  select distinct on (docid) s.*, a.allowed
  from
    (%(search)s) s
  join upaths p using (docid)
  join ace a on (
    a.docid = p.ancestor_docid and
    a.permission in ('%(permission)s', '*') and
    a.who in %(principals)s
    )
  order by s.docid, p.ord, a.ord
) _
where allowed
"""

def upath_filteredsearch(cursor, search, permission, principals, extra=''):
    return filteredsearch(cursor, search, permission, principals, extra,
                          template=upath_template)

array_template = """
with recursive
     text_results as (%(search)s),
     allowed(docid, id, parent_docid, allowed %(extra)s) as (
         select r.docid, r.docid as id, p.parent_docid,
                check_access(a.acl, array%(principals)s, '%(permission)s')
                %(extra)s
         from text_results r
         join parents p using (docid)
         left join acl a on (a.docid = r.docid)
     union all
         select allowed.docid, p.docid as id, p.parent_docid,
                check_access(a.acl, array%(principals)s, '%(permission)s')
                %(extra)s
         from allowed, parents p
         left join acl a on (a.docid = p.docid)
         where allowed.allowed is null and
               allowed.parent_docid = p.docid
    )
select docid %(extra)s from allowed where allowed
"""

def array_filteredsearch(cursor, search, permission, principals, extra=''):
    principals = list(principals)
    return filteredsearch(cursor, search, permission, principals, extra,
                          template=array_template)
