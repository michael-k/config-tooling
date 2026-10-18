# Security Invariants

These invariants bind every spec in the tree. A spec upholds an invariant by
saying so in its `## Security invariants` section. A spec that cannot uphold
one does not get to quietly narrow it: it names the invariant it bends,
claims a numbered allowance on its `**Allowances claimed:**` line, and the
allowance register below names the compensating control. `make spec-check`
enforces the pairing in both directions — an allowance with no claimant, or
a claim with no matching row, is a failure. Invariants are cited by specs,
not by code.

The tooling runs on a developer's machine, inside the repository that uses
it. It never deploys anything, so its invariants are about what it may
touch and what it may leak, not about a host's posture.

## Invariants

### INV-1 — Only its own machines and its own repository

THE Tooling SHALL act only on machines it launched under Incus and on files
of the repository that runs it.

**Why:** The toolkit force-deletes machines and the checker writes into the
spec tree. A toolkit that could reach a machine it did not launch could
delete or reconfigure a developer's own, and a checker that wrote outside
its repository could change a sibling's tree from the wrong working
directory. Both are tools a developer runs without reading first, so the
bound has to be in the tool.

### INV-2 — Throwaway credentials stay with their machine

THE Tooling SHALL generate every credential it creates for one machine, and
SHALL never write one into a repository or print one.

**Why:** A test machine needs a key to be reached, and that key is worth
nothing as long as it opens only that machine and is gone with it. A key
committed to a repository or printed into a CI log outlives the machine and
is readable by anyone who reads either.

### INV-3 — No value on an argument list

THE Tooling SHALL never place a value it passes to Ansible on a process
argument list.

**Why:** A process's argument list is readable by every user on the machine
through `ps` and `/proc`. The values a test passes to a playbook include
password hashes and, in a consumer's suite, keys; passing them in a file
that only the developer can read keeps them out of that list.

## Allowance register

| Allowance | Invariants | Claimed by | Compensating control |
|---|---|---|---|
