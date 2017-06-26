# commissaire-service v
Ignoring git+https://github.com/projectatomic/commissaire.git (-r requirements.txt (line 5))
To install it run: pip install git+https://github.com/projectatomic/commissaire.git

0.0.6
```
* 51d1925: storage: Add CustodiaStoreHandler.
* c2cf399: Require custodia.
* 356c384: docker: Add Dockerfile
* 6c6bfd6: investigator: Update for secret models
* d84b652: clusterexec: Update for secret models
* 2ca7fdd: watcher: Update for secret models
* 8940609: Post-release version bump.
```

# commissaire-service v0.0.5
```
* a047b49: test: Fix typo in test_service_containermgr.py.
* cd78d58: containermgr: Update container managers through notifications.
* c2ccabf: storage: Enable notification messages in handlers.
* 062dded: storage: Merge StoreHandlerManager into StorageService.
* 6b93fba: storage: Remove unused StoreHandlerManager.list_container_managers().
* aaa2d04: service: Use the connection's default channel.
* 7a04211: Post-release version bump.
```

# commissaire-service v0.0.4
```
* cabb32e: investigator: Fix typo.
* 3c78f25: service: Added bus-uri and exchange-name to config files
* 45845ce: Post-release version bump.
```

# commissaire-service v0.0.3
```
* 3110c18: storage: Clarify docs for list() method.
* c167388: storage: Give storage handlers a unique name.
* 62d3441: storage: Fix logging of ValidationErrors.
* 79e09c3: storage: Remove 'cluster_type' arg from list_container_managers().
* 44203f7: storage: Honor Host.source attribute.
* b4f3be7: storage: Rework data structure for extra handlers.
* 4ff49fb: storage: Remove StoreHandlerManager.get_logger().
* 6893f06: storage: Remove StoreHandlerManager.clone().
* 815339c: Use new host status constants.
* 254c321: investigator: inactive is no longer a valid status
* 8c88ede: transport: Log when subprocess completes.
* 91b702b: investigator: Fix handling of hosts with no cluster.
* 542d8a6: transport: Remove unused 'cluster' arg from bootstrap().
* 8eaedc4: service: get_oscmd now raises OSCmdError
* 4d5c876: service: --bus-uri no longer has a default
* 2dcd844: storage: Bypass code coverage requirement.
* c9e0c1b: storage: Accept list of homogeneous models.
* 546960d: clusterexec: Force serial work
* 8498841: containermgr: Cleanups around ContainerManagerError.
* 2dece68: service: Handle any RemoteProcedureCallError subclass.
* b284e3c: Post-release version bump.
```

# commissaire-service v0.0.2
```
* 7594271: containermgr: Add remove_all_nodes() method.
* 928f672: containermgr: Take an argument tuple in _node_operation().
* 92d4a3e: containermgr: Terminology: "manager", not "handler".
* 2a1cce6: containermgr: Fix class docstring.
* bf37ca0: containermgr: Revise API semantics.
* a8d4331: investigator: Call 'container.register_node'.
* f0b26ab: containermgr: Remove ContainerHandlerManager.
* 83f27d0: containermgr: Add refresh_managers() method.
* 1caa4c4: containermgr: Remove "list-handlers" method.
* 3472f69: containermgr: ContainerHandlers no longer come from config file.
* 04d935f: requirements: Bump ansible version.
* 334876e: Use commissaire.util.config.import_plugin().
* cce65b2: Added new style params to flanneld template
* da1b24e: bug: Fixes config argument issue in service scripts.
* c6b8ac6: service: Add add_service_arguments() for common CLI args.
* d2a1521: CommissaireService: Catch StorageLookupError exceptions.
* 5f1b9cd: CommissaireService: Use JSON-RPC error constants.
* c207529: Call read_config_file() for all services.
* 9a17afb: Add configuration files for all services.
* a7fd95a: tools: Remove etcd_init.sh.
* bb3decc: clusterexec: Return a dict instead of a JSON string.
* 935d5aa: storage: Now using it's own default configuration file.
* 3d8d66a: containermgr-service: Now using it's own default config file.
* 5be6096: ContainerManagerService (#35)
* b570f53: Update systemd units (#36)
* dd81a36: Use StorageClient to talk to storage service.
* 339b4f6: storage: Drop 'secure' arg from get() and list() methods.
* f270247: clusterexec: Enumerate hosts more efficiently.
* 17f8534: Simplify formatted strings.
* a14fb0c: Use commissaire.util.date.formatted_dt().
* e408ae5: Handle atomic hosts appropriately.
* afa7d07: storage: Drop 'secure' argument in save().
* c88dbc0: investigator: Include hidden attrs when converting to JSON.
* de9b0da: investigator: Partially adapt to ContainerManagerConfig.
* a52ee90: ansibleapi: Logging tweaks.
* cb730e6: ansibleapi: Don't retry after successful Ansible play.
* ac5d5fc: Apply playbooks to all hosts.
* a284f46: setup.py: Add package_data for playbooks and templates
* 88703ee: Add ClusterExecService.
* 9be5cd7: systemd: Added basic systemd units for services.
* 53d3bda: storage: Updated default storage config.
* f6852e2: Watcher Port (#25)
* 9519800: build: requirements files now have licenses.
* dceda19: storage: Use underscores in config data lookups.
* 9e03d11: storage: Accept model data as dict or string.
* 4f30a83: storage: Use super() to chain up.
* d182a15: Require Ansible 2.1.
* ab311c9: storage: Fix bug constructing model from JSON arg.
* b070229: Remove get_info.yaml playbook.
* 2c8141e: boostrap.yaml: Collect is_atomic variable.
* 0812acd: ansibleapi: Run method no longer returns facts.
* 9e53465: Rewrite Ansible driver.
* de7cdf2: Add an investigator service.
* 14fd3f4: StorageService: Add node_registered() bus method.
* 0d6d080: StorageService: Add "list_store_handlers" bus method.
* b7f0cfc: StoreHandlerManager: list_store_handlers() bugfix
* 0823b15: Remove Kubernetes templates.
* 9a9e70f: Remove Kubernetes variables from Ansible playbooks.
* db62eae: Remove Kubernetes definitions from OS command modules.
* 4474326: Add an Ansible transport, playbooks and templates.
* 601ef0a: Add OS-specific command modules.
* 964cf95: .redhat-ci.yml: Add package openssl-devel.
* dc10d00: .redhat-ci.yml: Add package redhat-rpm-config.
* 034aea5: .redhat-ci.yml: switch to containerized builds
* 52da60f: tools: Added etcd_init.sh (#18)
* 98a9700: Add dependency for Redis
* 723d160: test: Updates to enable redhat-ci.
* 035b0bc: test: Added nose-htmloutput to test requirements.
* 388a854: storage-service: Added optional secure parameter. (#15)
* cd0ca30: bug: Fix double encoding issue in storage responses. (#13)
* ec5c52b: storage: -c / --config is not required.
* cca3175: Allow 'params' to be optional in JSON-RPC requests.
* 67140e6: storage: commissaire-storage-service now installs as a bin.
* dd30d7d: bug: Change _build_model to take a dictionary. (#10)
* b95ef09: Fixed config module imports.
* bed2a27: test: Updated repo for Travis/Jenkins CI usage through tox. (#7)
* 2c5ed18: Moved config function use to commissaire.config.
* 33ccbce: Response messages should be valid JSON-RPC responses. (#6)
* 2e451c8: Add storage service to API docs.
* ad50832: CommissaireService now takes advantage of commissaire.bus.BusMixin.
* a55fe11: flake8: Fixed flake8 issues.
* b3a6105: Add a basic Storage service.
* 7bde280: Log tracebacks when handling method exceptions. (#2)
* 007c222: Message bodies can now be delivered as dict or json strings.
* 1467771: doc: Updated README.md wording.
* 8d41163: Removed object deletion hook.
* 3de2e2c: message now the first argument in all on_ methods.
* 13e1201: Checking instance type of body before processing.
* 3ad8417: Added unittests.
* 31d264c: Replaced autorun with run_service.
* 7395959: send_request/response methods renamed request/respond.
* 841624f: doc: Added specific run examples.
* 8fe9db7: Changed the example for documentation.
* 81ef08f: doc: Added basic documentation.
* 232ba80: Added ServiceManager class.
* 5700788: Errors now ack and return error structs.
* 9ebf4b9: Now using jsonrpc for message format.
* c7cda22: Now using topic exchange.
* 2b25a7e: send_msg() now split into send_response() and send_request().
* 230192b: Added send_msg().
* 31c53e1: Added actions.
* f04d15d: example: Added in storage stub.
```
