from collections import defaultdict

def walk(ob, func, limit=-1):
    if limit == 0:
        return
    func(ob)
    if hasattr(ob, 'values'):
        for v in ob.values():
            walk(v, func, limit-1)


access_bool = dict(allow='1', deny='0')

def acls(fname):

    file = open(fname, 'w')

    from pyramid.security import AllPermissionsList
    all_permissions = '*',

    def save(ob):
        docid = str(ob.docid)
        for ord, a in enumerate(getattr(ob, '__acl__', ())):
            access, who, permissions = a
            if permissions.__class__ == AllPermissionsList:
                permissions = all_permissions
            for p in permissions:
                file.write('\t'.join(
                    (access_bool[access.lower()], who, p, docid, str(ord))
                    ) + '\n')

    return save

def aces(fname):

    file = open(fname, 'w')

    from pyramid.security import AllPermissionsList
    all_permissions = '*',

    def save(ob):
        docid = str(ob.docid)
        aces = []
        acl = getattr(ob, '__acl__', ())
        if acl:
            for access, who, permissions in acl:
                if permissions.__class__ == AllPermissionsList:
                    permissions = all_permissions
                permissions = ', '.join('"%s"' % p for p in permissions)
                aces.append("row(%s, '%s', '{%s}')" % (
                    access_bool[access.lower()], who, permissions))
            file.write(
                "insert into acl values (%s, ARRAY[%s]::Access[]);\n" % (
                    docid, ', '.join(aces)))

    return save

def parents(fname):
    file = open(fname, 'w')

    def save(ob):
        file.write('%s\t%s\n' % (ob.docid, ob.__parent__.docid))

    return save

