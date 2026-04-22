---
spark: true
scf_file_role: "skill"
scf_version: "1.2.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---

# MCP Tool Index

- runtime: `scf_get_runtime_state`, `scf_update_runtime_state`
- inventory: `scf_list_agents`, `scf_list_skills`, `scf_list_instructions`, `scf_list_prompts`
- config: `scf_get_project_profile`, `scf_get_global_instructions`, `scf_get_model_policy`
- packages: `scf_list_available_packages`, `scf_get_package_info`, `scf_install_package`, `scf_remove_package`