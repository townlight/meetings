# Townlight Beta 1 developer checks

The suite MSI is signed. The standalone Meetings installer built from this
repository is a different artifact; Windows may show Unknown Publisher for
that unsigned development build, or a "Windows protected your PC" prompt.
Use the signed suite MSI for beta installation.

The existing connector runtime validation remains a developer check, not proof
that a city has configured every vendor. From the repository root:

```powershell
python scripts/run_mock_city_environment_suite.py --help
python scripts/check_starter_set_integration.py --help
python scripts/run_mock_city_environment_suite.py --hostile-mode
```

These tools use synthetic/mock-city data. The exact suite acceptance and limits
are in the Townlight Beta 1 manual and release provenance; these commands do not
replace the signed-candidate Sandbox receipts.
