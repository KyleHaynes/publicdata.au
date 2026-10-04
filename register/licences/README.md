# Licence grants

A dataset may carry a licence that is not a Creative Commons licence when the publisher's own
words grant everything a republication needs. Each such grant is one file here, named by its id,
and `register validate` refuses a file that does not quote the publisher on all four of:

1. `reproduce`: reproduction and redistribution to the public, since every version is a copy;
2. `adapt`: adaptation, since format conversion, typed columns and partitions are adaptations;
3. `commercial`: use by a company, quoted, or `silent` when the grant does not limit it;
4. `attribution`: the attribution form the publisher asks for.

A grant that fails any one of these is not admitted, and the dataset stays `blocked` until the
publisher writes to lift it. A written permission is its own grant with `kind: permission`, an id
of the form `<AGENCY>-PERMISSION-<year>`, and the reply stored under `letters/` and named in
`letter`. `read` is the date a person read the words on the publisher's page or in the letter.
`hub` is the licence name the data hubs show, which for every grant here is `other`.
