# Publishing MSCH Nodes

One repository and one Registry package: **`msch-comfyui-nodes`**, display name **MSCH Nodes**, publisher **mariobilly**.

The root `pyproject.toml` contains the only release version. The **Publish to Comfy Registry** GitHub workflow validates the pack, then uses the repository secret `REGISTRY_ACCESS_TOKEN` to upload it. The workflow runs manually or when a GitHub release is published.

The first unified release is `0.1.0`. It is distinct from the old component packages' versions. Its [publishing workflow](https://github.com/mariobilly/msch-comfyui-nodes/actions/runs/34044024968) succeeded. The uploaded archive contains all 35 node IDs, was downloaded and verified, and excludes large showcase media. Registry reported `NodeVersionStatusPending` at verification; activation is still external. The older 15-package records are historical and are not the unified pack's release history.

The Manager node-list submission is [PR #3247](https://github.com/Comfy-Org/ComfyUI-Manager/pull/3247), updated to register this one repository. Registry processing and Manager list acceptance are external steps; a successful upload alone does not prove that a version is active in Manager.

For future updates, change the root version once and publish the complete pack. See [CONTRIBUTING.md](CONTRIBUTING.md).

[Verified release record](registry-releases.json) · [Registry page](https://registry.comfy.org/nodes/msch-comfyui-nodes)
