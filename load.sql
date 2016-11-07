create temp table parents (
  docid int primary key,
  parent_docid int not null);
create temp table paths (
  docid int primary key,
  path varchar not null);
create temp table upaths (
  docid int not null,
  ancestor_docid int not null,
  ord int not null);
create temp table ace (
  docid int not null,
  allowed bool not null,
  who varchar not null,
  permission varchar not null,
  ord int not null);

create type Access as (allowed bool, who varchar, permissions varchar[]);
create temp table acl (docid int primary key, acl Access[]);

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

\copy parents (docid, parent_docid) from 'aa.parents';
\copy paths (docid, path) from 'aa.paths';
\copy upaths (docid, ancestor_docid, ord) from 'aa.upaths';
\copy ace (allowed, who, permission, docid, ord) from 'aa.acls';
\i aa.aces.sql

create index on parents using hash (docid);
create index on acl using hash (docid);
create index on ace (docid, permission, who);
create index on upaths(docid);

create temp table pace as
select p.path || '%' as pathp, a.allowed, a.who, a.permission, a.ord
from paths p join ace a using (docid);
create index on pace (permission, who);

analyze parents;
analyze ace;
analyze acl;
analyze paths;
analyze pace;
analyze upaths;

\timing

\echo base search

select count(*) from (
  select docid from pgtextindex
  where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983'
  ) _;

select count(*) from (
  select docid from pgtextindex
  where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983'
  ) _;

explain select count(*) from (
  select docid from pgtextindex
  where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983'
  ) _;

\echo recursive filtered search

select count(*) from (
  with recursive
       text_results as (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983'),
       allowed(docid, id, parent_docid, allowed ) as (
         select docid, id, parent_docid, allowed  from (
           select distinct on (r.docid)
                  r.docid, r.docid as id, p.parent_docid, a.allowed 
           from text_results r
           join parents p using (docid)
           left join ace a on (
             a.docid = r.docid and
             a.permission in ('edit', '*') and
             a.who in ('USER', 'GROUP', 'system.Everyone')
             )
           order by r.docid, a.ord
           ) base
       union all
         select docid, id, parent_docid, allowed  from (
           select distinct on (p.docid)
                  p.docid, p.id, p.parent_docid, a.allowed 
           from (select allowed.docid, p.docid as id, p.parent_docid 
                 from allowed, parents p
                 where allowed.allowed is null and
                       allowed.parent_docid = p.docid) p
                left join ace a on (
                  a.docid = p.id and
                  a.permission in ('edit', '*') and
                  a.who in ('USER', 'GROUP', 'system.Everyone')
                  )
           order by p.docid, a.ord
           ) recursive
       )
  select docid  from allowed where allowed
  ) _;

select count(*) from (
  with recursive
       text_results as (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983'),
       allowed(docid, id, parent_docid, allowed ) as (
         select docid, id, parent_docid, allowed  from (
           select distinct on (r.docid)
                  r.docid, r.docid as id, p.parent_docid, a.allowed 
           from text_results r
           join parents p using (docid)
           left join ace a on (
             a.docid = r.docid and
             a.permission in ('edit', '*') and
             a.who in ('USER', 'GROUP', 'system.Everyone')
             )
           order by r.docid, a.ord
           ) base
       union all
         select docid, id, parent_docid, allowed  from (
           select distinct on (p.docid)
                  p.docid, p.id, p.parent_docid, a.allowed 
           from (select allowed.docid, p.docid as id, p.parent_docid 
                 from allowed, parents p
                 where allowed.allowed is null and
                       allowed.parent_docid = p.docid) p
                left join ace a on (
                  a.docid = p.id and
                  a.permission in ('edit', '*') and
                  a.who in ('USER', 'GROUP', 'system.Everyone')
                  )
           order by p.docid, a.ord
           ) recursive
       )
  select docid  from allowed where allowed
  ) _;

explain select count(*) from (
  with recursive
       text_results as (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983'),
       allowed(docid, id, parent_docid, allowed ) as (
         select docid, id, parent_docid, allowed  from (
           select distinct on (r.docid)
                  r.docid, r.docid as id, p.parent_docid, a.allowed 
           from text_results r
           join parents p using (docid)
           left join ace a on (
             a.docid = r.docid and
             a.permission in ('edit', '*') and
             a.who in ('USER', 'GROUP', 'system.Everyone')
             )
           order by r.docid, a.ord
           ) base
       union all
         select docid, id, parent_docid, allowed  from (
           select distinct on (p.docid)
                  p.docid, p.id, p.parent_docid, a.allowed 
           from (select allowed.docid, p.docid as id, p.parent_docid 
                 from allowed, parents p
                 where allowed.allowed is null and
                       allowed.parent_docid = p.docid) p
                left join ace a on (
                  a.docid = p.id and
                  a.permission in ('edit', '*') and
                  a.who in ('USER', 'GROUP', 'system.Everyone')
                  )
           order by p.docid, a.ord
           ) recursive
       )
  select docid  from allowed where allowed
  ) _;

\echo path filtered search

select count(*) from (
  select docid  from (
    select distinct on (docid) s.*, a.allowed
    from
      (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983') s
    join paths p using (docid)
    join pace a on (
      p.path like a.pathp and
      a.permission in ('edit', '*') and
      a.who in ('USER', 'GROUP', 'system.Everyone')
      )
    order by s.docid, a.pathp desc, a.ord
  ) _
  where allowed
  ) _;

select count(*) from (
  select docid  from (
    select distinct on (docid) s.*, a.allowed
    from
      (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983') s
    join paths p using (docid)
    join pace a on (
      p.path like a.pathp and
      a.permission in ('edit', '*') and
      a.who in ('USER', 'GROUP', 'system.Everyone')
      )
    order by s.docid, a.pathp desc, a.ord
  ) _
  where allowed
  ) _;

explain select count(*) from (
  select docid  from (
    select distinct on (docid) s.*, a.allowed
    from
      (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983') s
    join paths p using (docid)
    join pace a on (
      p.path like a.pathp and
      a.permission in ('edit', '*') and
      a.who in ('USER', 'GROUP', 'system.Everyone')
      )
    order by s.docid, a.pathp desc, a.ord
  ) _
  where allowed
  ) _;

\echo unnested path filtered search

select count(*) from (
  select docid  from (
    select distinct on (docid) s.*, a.allowed
    from
      (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983') s
    join upaths p using (docid)
    join ace a on (
      a.docid = p.ancestor_docid and
      a.permission in ('edit', '*') and
      a.who in ('USER', 'GROUP', 'system.Everyone')
      )
    order by s.docid, p.ord, a.ord
  ) _
  where allowed
  ) _;

select count(*) from (
  select docid  from (
    select distinct on (docid) s.*, a.allowed
    from
      (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983') s
    join upaths p using (docid)
    join ace a on (
      a.docid = p.ancestor_docid and
      a.permission in ('edit', '*') and
      a.who in ('USER', 'GROUP', 'system.Everyone')
      )
    order by s.docid, p.ord, a.ord
  ) _
  where allowed
  ) _;


explain select count(*) from (
  select docid  from (
    select distinct on (docid) s.*, a.allowed
    from
      (select docid from pgtextindex where text_vector @@ 'zuma'::tsquery and community_docid = '-1601401983') s
    join upaths p using (docid)
    join ace a on (
      a.docid = p.ancestor_docid and
      a.permission in ('edit', '*') and
      a.who in ('USER', 'GROUP', 'system.Everyone')
      )
    order by s.docid, p.ord, a.ord
  ) _
  where allowed
  ) _;


\echo array recursive filtered search

select count(*) from (
  with recursive
     text_results as (
       select docid
       from pgtextindex
       where text_vector @@ 'zuma'::tsquery and
             community_docid = '-1601401983'),
     allowed(docid, id, parent_docid, allowed ) as (
         select r.docid, r.docid as id, p.parent_docid,
                check_access(
                  a.acl,
                  array['USER',
                        'GROUP',
                        'system.Everyone'],
                  'edit')
                
         from text_results r
         join parents p using (docid)
         left join acl a on (a.docid = r.docid)
     union all
         select allowed.docid, p.docid as id, p.parent_docid,
                check_access(
                  a.acl,
                  array['USER',
                        'GROUP',
                        'system.Everyone'],
                  'edit')
                
         from allowed, parents p
         left join acl a on (a.docid = p.docid)
         where allowed.allowed is null and
               allowed.parent_docid = p.docid
    )
  select docid  from allowed where allowed
  ) _;

select count(*) from (
  with recursive
     text_results as (
       select docid
       from pgtextindex
       where text_vector @@ 'zuma'::tsquery and
             community_docid = '-1601401983'),
     allowed(docid, id, parent_docid, allowed ) as (
         select r.docid, r.docid as id, p.parent_docid,
                check_access(
                  a.acl,
                  array['USER',
                        'GROUP',
                        'system.Everyone'],
                  'edit')
                
         from text_results r
         join parents p using (docid)
         left join acl a on (a.docid = r.docid)
     union all
         select allowed.docid, p.docid as id, p.parent_docid,
                check_access(
                  a.acl,
                  array['USER',
                        'GROUP',
                        'system.Everyone'],
                  'edit')
                
         from allowed, parents p
         left join acl a on (a.docid = p.docid)
         where allowed.allowed is null and
               allowed.parent_docid = p.docid
    )
  select docid  from allowed where allowed
  ) _;

explain select count(*) from (
  with recursive
     text_results as (
       select docid
       from pgtextindex
       where text_vector @@ 'zuma'::tsquery and
             community_docid = '-1601401983'),
     allowed(docid, id, parent_docid, allowed ) as (
         select r.docid, r.docid as id, p.parent_docid,
                check_access(
                  a.acl,
                  array['USER',
                        'GROUP',
                        'system.Everyone'],
                  'edit')
                
         from text_results r
         join parents p using (docid)
         left join acl a on (a.docid = r.docid)
     union all
         select allowed.docid, p.docid as id, p.parent_docid,
                check_access(
                  a.acl,
                  array['USER',
                        'GROUP',
                        'system.Everyone'],
                  'edit')
                
         from allowed, parents p
         left join acl a on (a.docid = p.docid)
         where allowed.allowed is null and
               allowed.parent_docid = p.docid
    )
  select docid  from allowed where allowed
  ) _;
