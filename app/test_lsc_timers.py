import json
import unittest
from unittest.mock import MagicMock
from core import ControlError
from lsc_timers import timer_payload, save_timer, set_timer_status
from lsc_planning import timer_rows, repeat_label

class TimerTests(unittest.TestCase):
    def setUp(self):
        self.item = {"device_id":"bulb","lsc_home_id":42,"lsc_timezone":"Europe/Paris",
                     "lsc_functions":{"switch_led":{"id":"20"}}}
        self.form = {"time":"06:00","loops":"0111110","power":True,
                     "enabled":True,"notify":True,"alias":"Matin"}

    def test_weekdays_match_the_mobile_sunday_first_encoding(self):
        self.assertEqual(repeat_label("0111110"),"Du lundi au vendredi")
        self.assertEqual(repeat_label("1000001"),"Dim, Sam")

    def test_edit_preserves_other_dps_and_timezone_metadata(self):
        timer = {"timerId":123,"dps":{"20":False,"22":350}, "params":{"keep":True},
                 "date":"00000000","timezoneId":"Europe/Paris"}
        payload = timer_payload(self.item,self.form,timer)
        action = json.loads(payload["actions"])
        self.assertEqual(action["dps"],{"20":True,"22":350})
        self.assertEqual(action["params"],{"keep":True})
        self.assertEqual(action["date"],"00000000")
        self.assertEqual(action["timezoneId"],"Europe/Paris")
        self.assertEqual(payload["id"],123)
        self.assertTrue(payload["isAppPush"])

    def test_invalid_form_never_reaches_the_cloud(self):
        for field,value in (("time","24:00"),("loops","weekday"),("enabled",1),("notify",None),("power","true")):
            with self.subTest(field=field):
                account=MagicMock()
                with self.assertRaises(ControlError):save_timer(account,self.item,dict(self.form,**{field:value}))
                account.request.assert_not_called()

    def test_disabled_test_timer_cannot_execute(self):
        payload=timer_payload(self.item,dict(self.form,enabled=False,notify=False))
        self.assertEqual(payload["status"],0)
        self.assertFalse(payload["isAppPush"])

    def test_delete_targets_only_the_explicit_timer_id(self):
        account=MagicMock();account.request.return_value=True
        set_timer_status(account,self.item,123,2)
        self.assertEqual(account.request.call_args.args[1],
                         {"bizId":"bulb","bizType":0,"ids":"123","status":2})

    def test_cloud_refusal_is_not_reported_as_success(self):
        account=MagicMock();account.request.return_value=False
        with self.assertRaises(ControlError):set_timer_status(account,self.item,123,1)

    def test_grouped_timers_retain_their_own_ids(self):
        rows=timer_rows([{"category":{"category":"switch_led","status":1},
            "groups":[{"id":"group","timers":[{"timerId":2,"time":"07:00"},
                      {"timerId":1,"time":"06:00"}]}]}])
        self.assertEqual([r["timerId"] for r in rows],[1,2])
        self.assertTrue(all(r['group_id']=='group' for r in rows))

if __name__ == '__main__':unittest.main()
