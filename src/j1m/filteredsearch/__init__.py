
sql = """
with recursive
     text_results as (%(search)s),
     allowed(docid, id, parent_docid, allowed) as (
       select docid, id, parent_docid, allowed from (
         select distinct on (r.docid)
                r.docid, r.docid as id, p.parent_docid, a.allowed
         from text_results r
         join parents p using (docid)
         left join ace a using (docid)
         order by r.docid, a.ord
         ) base
     union all
       select docid, id, parent_docid, allowed from (
         select distinct on (p.docid)
                p.docid, p.id, p.parent_docid, a.allowed
         from (select allowed.docid, p.docid as id, p.parent_docid
               from allowed, parents p
               where allowed.allowed is null and
                     allowed.parent_docid = p.docid) p
              left join ace a on (a.docid = p.id)
         order by p.docid, a.ord
         ) recursive
     )
select docid from allowed where allowed

"""

def filteredsearch(cursor, search, permission, principals):
    principals = repr(principals).replace(',)', ')')
    cursor.execute(sql % dict(
        search=search, permission=permission, principals=principals))
    return cursor.fetchall()
