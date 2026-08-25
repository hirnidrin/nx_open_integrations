// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/

# Nx Meta VMP Open Integrations

---------------------------------------------------------------------------------------------------
## Introduction

This repository `nx_open_integrations` contains **Network Optix Meta Video Management Platform
open source integration examples** - the source code and specifications which show how to integrate
a third-party solution with the Nx Meta Video Management Platform (VMP) and thus all Powered-By-Nx
products, including Nx Witness Video Management System (VMS).

There are several branches in the repository corresponding to the VMS releases: vms_5.0, vms_5.1.
The master branch corresponds to the current development version of the VMS. Code examples in the 
branch do not necessary work with the release versions. 

Pay your attention to which branch you are about to use.

Most of the source code and other files are licensed under the terms of Mozilla Public License 2.0
(unless specified otherwise in the files) which can be found in the license_mpl2.md file in the
root directory of the repository.

For details about the components, see `readme.md` files in sub-folders.

---------------------------------------------------------------------------------------------------
## Free and Open-Source Software Notices

For the legal information on third-party projects involved, see `notice.md` files in sub-folders.

---------------------------------------------------------------------------------------------------
## How we use this fork

This is a personal fork (`hirnidrin/nx_open_integrations`) used for experiments with the Nx
integration samples — it is not a contribution channel back to Network Optix, and no pull requests
are submitted upstream.

* `master` only tracks the forked upstream repository; it is never worked on directly.
* `playground` is the reference branch where our own work lives, either directly or via feature
  branches merged back into it.
* Our commits use semantic subjects (`feat:`, `fix:`, `docs:`, `chore:`), unlike the `VI-xx:`
  ticket prefixes in upstream history.
* Development happens inside the dev container — see `.devcontainer/README.md` and `CLAUDE.md`.
