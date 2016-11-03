
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

def filteredsearch(cursor, search, permission, principals, extra=''):
    principals = repr(principals).replace(',)', ')')
    sql = template % dict(
        search=search, permission=permission, principals=principals,
        extra=extra)
    if cursor is None:
        print(sql)
    else:
        cursor.execute(sql)
        return cursor.fetchall()
