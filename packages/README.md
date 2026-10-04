# Catalog packages

The Control Plane catalog — task and artifact types, roles, capabilities, skills, work
rules, processes, calendars, agent descriptions and notification rules — is stored in
git as packages: a `packages/<key>/` directory with `package.yaml` and YAML object
files in the `{apiVersion, kind, key, spec}` envelope. The format's schemas (objects,
process tests, installation plans) ship with the package SDK, the `sdk/package-sdk`
submodule: `sdk/package-sdk/schema/v1/object.schema.json` and its neighbours.

Which packages to install into an installation is defined by the install file
[deploy/packages.yaml](../deploy/packages.yaml); `make bootstrap` applies it at step 5b
as one installation plan, and a repeated run changes only what differs. The tool is
the package SDK (`sdk/package-sdk`):

```bash
make packages-check                                  # check without a running installation
make packages-plan  SERVER=http://taimen.localhost   # the plan for a live Control Plane, writes nothing
make packages-apply SERVER=http://taimen.localhost   # apply exactly that plan
uv run --project sdk/package-sdk --all-extras package-sdk --help   # test, export, edit and the rest
```

The token for `plan` and `apply` is the `CP_TOKEN` variable (an access token for the
`control-plane` audience) or the operator's credential through the core client (extra
`package-sdk[connector]`). [example](example/) is a minimal sample package. For details,
see the package SDK's README, the guide's catalog packages section and its articles on
work rules and processes.
