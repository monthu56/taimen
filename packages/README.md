# Catalog packages

The Control Plane catalog — task and artifact types, roles, capabilities, skills, work
rules, processes, calendars, agent descriptions and notification rules — is stored in
git as packages: a `packages/<key>/` directory with `package.yaml` and YAML object
files in the `{apiVersion, kind, key, spec}` envelope. The object schema is
[schema/v1/object.schema.json](schema/v1/object.schema.json), the process test schema
is [schema/v1/test.schema.json](schema/v1/test.schema.json).

Which packages to install into an installation is defined by the install file
[deploy/packages.yaml](../deploy/packages.yaml). The tool is `tools/cp_packages.py`:

```bash
make packages-check                                  # check without a running installation
make packages-plan  SERVER=http://taimen.localhost   # what will change in a live Control Plane
make packages-apply SERVER=http://taimen.localhost   # apply
python3 tools/cp_packages.py --help                  # test, export, migrate-expr and the rest
```

The token for `plan` and `apply` is the `CP_TOKEN` variable (an access token for the
`control-plane` audience) or the operator's credential, if the tool is run by the
interpreter of the installed control-plane package. [example](example/) is a minimal
sample package. For details, see the guide's catalog packages section and its articles
on work rules and processes.
