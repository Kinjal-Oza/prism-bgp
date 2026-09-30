for c in PT2008 PT2008_ctl TM2015 TM2015_ctl RT2017 RT2017_ctl DV2017 DV2017_ctl AM2018 AM2018_ctl MO2018_ctl DQ2019 DQ2019_ctl RT2020 RT2020_ctl; do echo $c; done | xargs -P2 -I{} sh -c 'python3 run_case.py {} > out/{}.log 2>&1'
echo ALLDONE > out/ALLDONE
