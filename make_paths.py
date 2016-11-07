import sys

def main():
    inp, outp = sys.argv[1:]

    parents = {
        docid: parent_docid
        for (docid, parent_docid)
        in [l.split('\t') for l in open(inp).read().strip().split('\n')]
        }

    def path(docid):
        if docid is None:
            return '/'
        else:
            parent = parents.get(docid)
            return path(parent) + (str(docid) + '/')

    open(outp, 'w').writelines(
        "%s\t%s\n" % (docid, path(docid))
        for docid in parents)

if __name__ == '__main__':
    main()

