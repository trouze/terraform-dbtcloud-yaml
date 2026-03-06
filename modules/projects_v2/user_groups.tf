#############################################
# User Groups (account-level, maps users to group IDs)
# No delete support — manages group membership only.
#############################################

resource "dbtcloud_user_groups" "assignments" {
  for_each = local.user_groups_map

  user_id   = each.value.user_id
  group_ids = each.value.group_ids

  depends_on = [
    dbtcloud_group.groups,
    dbtcloud_group.protected_groups,
  ]
}
