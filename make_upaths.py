import sys

def main():
    inp, outp = sys.argv[1:]

    parents = {
        docid: parent_docid
        for (docid, parent_docid)
        in [l.split('\t') for l in open(inp).read().strip().split('\n')]
        }

    def path(docid):
        while docid is not None:
            yield docid
            docid = parents.get(docid)

    with open(outp, 'w') as out:
        for docid in parents:
            for ord, ancestor in enumerate(path(docid)):
                out.write("%s\t%s\t%s\n" % (docid, ancestor, ord))

if __name__ == '__main__':
    main()

