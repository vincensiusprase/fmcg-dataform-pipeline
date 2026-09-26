// includes/constants.js
// Shared business constants for the FMCG inventory mart layer

const service_level_z = {
  // Z-score lookup for common service level targets
  "0.90": 1.28,
  "0.95": 1.65,
  "0.975": 1.96,
  "0.99": 2.33,
};

const default_service_level = "0.95";

const abc_cutoffs = {
  a_cum_pct: 0.75,
  b_cum_pct: 0.93,
};

module.exports = {
  service_level_z,
  default_service_level,
  abc_cutoffs,
};
