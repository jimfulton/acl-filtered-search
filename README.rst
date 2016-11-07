==========================================================
Exploration of hierarchical-security-filtered SQL searches
==========================================================

.. contents::

See:

- https://bugs.launchpad.net/karl4/+bug/1638295
- https://bugs.launchpad.net/karl4/+bug/1639043

In content-management systems based on object trees, access-control
statements made on node affect nodes below.

This project looked at ways to combine access checks with searches
made against a Postgres database.  Original data are in a ZODB-based
database and indexed with Postgres.  Search results are filtered in an
application by using access control lists (ACLs) in the object
database. The goal of this project was to look at ways to represent
ACLs in Postgres so they could be searched in Postgres as part of the
content search.

Access control algorithm
========================

The access control algorithm uses access control lists (ACLs) that are
optionally placed at nodes in a hierarchical tree of content objects.
ACLs are ordered lists of access control entries (ACEs). Each entry is
an allowed entry or a denied entry and has a principal (user, group)
id and a list of permission ids.  Access control checks ask whether a
principal has a permission for an object.  This is typically applied
for multiple principal ids (user id and ids of their groups)
associated with an execution context (e.g. web request).

The algorithm is recursive:

#. For an object, iterate over the object's ACL (if any) in oder until
   a matching ACE if found. An ACE matches if it is for the given
   principal and includes the desired permission.  If the ACE is a deny
   ACE, access is denied and the algorithm stops.  If the ACE is an allow
   ACE, access is allowed and the algorithm stops.

#. If the first step doesn't yield a decision and if the object has a
   parent, apply the check to the parent. If there is no parent, access
   is denied.

Some important things to note:

- The tree search searches up the tree looking for ancestors, as
  opposed to more common tree searches that look for descendents.

- The search is ordered, and stops when a decision can be made.
  Ordering is critical both when traversing the tree and when
  iterating over ACLs.

Approaches
==========

Three approaches were implemented:

#. Simple recursive algorithm using parents and flattened ACEs

   The hierarchy is represented using parent pointers and the algorithm
   is implemented recursively.

   ACEs are stored in flattened form by document id, permission and principal.

#. Recursive search representing ACLs as Postgres arrays

   In this variation of the recursive algorithm, ACLs were represented
   as arrays of ACEs.  This avoided sorting to find the first matching
   ACE at the cost of linear search of the ACLs to find the first
   matching ACE.

#. Materialized path

   The hierarchy is represented using path strings.  I used document
   ids to construct the paths, but names could have been used as well.

   ACEs are stored by path rather than by document ids, facilitating
   path-based joins.

   A potential advantage of this approach over recursive search is
   that we can do the search in a single join, rather than multiple
   joins applied recursively.

#. "Unnested" paths

   Rather than representing paths as strings, one could represent them
   as arrays of document ids.  Unfortunately, queries on arrays don't
   facilitate the sort of ordered queries we need.  To do ordered
   searches, one would typically unnest the arrays.  Rather than
   creating arrays and unnesting them, I just created a table that
   would have resulted from unnesting directly.

   As with the materialized path approach, a potential advantage of
   this approach is that we can do the search in a single join, rather
   than multiple joins applied recursively.

Other approaches that were not pursued:

- Adjacency list

  See:
  https://thesai.org/Downloads/Volume7No4/Paper_34-Improve_Query_Performance_On_Hierarchical_Data.pdf

  This model can make searching for node descendents very fast, but
  doesn't provide help with finding ancestors.

All of the approaches accepted a base search query. The only
requirement of the base query was that the results contained a
``docid`` column.  All of the approaches expressed hierarchy and ACLs
based on docids.

Simple recursive algorithm using parents and flattened ACEs
-----------------------------------------------------------

This approach used a parents table is used to represent hierarchy::

  create table parents (
    docid int primary key,
    parent_docid int not null);

  create index on parents using hash (docid);

And represented ACLs as flattened ACEs::

  create table ace (
    docid int not null,
    allowed bool not null,
    who varchar not null,
    permission varchar not null,
    ord int not null);
  create index on ace (docid, permission, who);

The recursive query was based on this template::

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

Some things to note about this approach:

- The recursive algorithm expresses hierarchy-based ordering. It
  expresses the recursive nature of the access control algorithm
  fairly directly.

- The ordering within ACLs is expressed with the ``ord`` column in the
  ``ace`` table.  To pick the first matching ACE, I use::

    select distinct on (docid)

  together with::

    order by docid, ord

  This requires a sort.  This seems to be mitigated a bit by the fact
  that the records are nearly sorted as a result of the way joins work.

- Using flattened ACEs allows indexed-based filtering of permissions
  and principals.

- I added a hash index on ``parents``. This seemed to provide better
  performance than the default BTree index provided by the primary key.

Recursive search representing ACLs as Postgres arrays
-----------------------------------------------------

In this approach, I use the same parents table::

  create table parents (
    docid int primary key,
    parent_docid int not null);

  create index on parents using hash (docid);

to represent hierarchy.  To represent ACLs, I use a custom type and a
table that represents ACLs using arrays::

  create type Access as (allowed bool, who varchar, permissions varchar[]);
  create table acl (docid int primary key, acl Access[]);
  create index on acl using hash (docid);

To search the ACLs, I had to provide a custom function::

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

The search template is a bit simpler::

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

Some things to note:

- ACE ordering and filtering is provided by the ``check_access``
  function.

- We no longer need to sort as part of the query (and we no longer
  leverage an index to filter).

Materialized path
-----------------

In this approach, hierarchy is presented via paths::

  create table paths (
    docid int primary key,
    path varchar not null);

For this analysis, the path segments were docids. Paths had leading a
trailing /s. (``/2118645230/-1601401983/-1601401982/1210636615/``)

ACLs were represented as flattened ACEs by path rather than docids::

  create table pace (
    path varchar not null,
    allowed bool not null,
    who varchar not null,
    permission varchar not null,
    ord int not null);
  create index on pace (permission, who);

The search was awkward. As with adjacency lists, path indexes are
mainly useful for finding descendents using like queries::

    path like '/foo/bar/%'

For security filtering, we need to search for ACEs for ancestors.
IOW, we needed to find ACEs for path prefixes::

    path like aclpath || '%'

To avoid the concatenation above, we included the trailing ``%`` in
the ACE paths.  The resulting query template::

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

Notes:

- We no longer use a recursive query.  Hierarchical search order is
  implemented by sorting by path (descending).

- The path sort is expensive (much more so than the ACL ``ord`` sort.

- The primary-key on the ``path`` column on the ``paths`` table wasn't
  used.  This was likely a result of the way the like search criteria
  was varying over rows of the ``pace`` table.

"Unnested" paths
----------------

Rather than using strings, we can represent paths as arrays of
docids.  These would be ancestor arrays. Unfortunately, Postgres
doesn't provide an ordered array search. Typically, to take order into
account, one unnests arrays into rows with a column indicating
original positions. Rather than doing that unnesting on the fly, I
created an unnested data structure::

  create temp table upaths (
    docid int not null,
    ancestor_docid int not null,
    ord int not null);
  create index on upaths(docid);

Here, we create a for each document and each of it's ancestors
(including itself).  We use an ``ord`` column to represent the
distance of the ancestor.

(A better name for this table would have been ancestors. :) )

For ACL data, I used the flattened ACEs::

  create table ace (
    docid int not null,
    allowed bool not null,
    who varchar not null,
    permission varchar not null,
    ord int not null);
  create index on ace (docid, permission, who);

The search template::

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

Note:

- This is very similar to the materialized path solution, except that
  we join ACL data based on ancestor id rather than path and we sort
  based on ancestor order rather than ACL path.

- Sorting didn't seem to be as much of an issue for this approach,
  probably because of the way the ancestor table clustered data by
  docid.

Performance results
===================

For the base search, I performed a simple search using a search term
and a "community" identifier than narrowed results to a subset of a
site.

The base search took around 4ms.

The recursive approaches took roughly the same time, which was around
15ms.

The materialized-path approach was by far the slowest, taking around
800ms.

The unnested path approach was a little bit slower than the recursive
approaches, taking around 20ms.

Timings tended to vary a bit.

Timings would also vary depending on the size of the base-search
result set to be filtered.

Conclusion
==========

The recursive solution using ACE arrays seems to be best because:

- It provided the best performance, tied with the other recursive
  approach.

- It provides a ACL representation that is compact and mirrors the
  representation in the application, making it easier to manage.
