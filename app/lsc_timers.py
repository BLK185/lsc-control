"""Validated shared timer operations. No independent desktop scheduler."""
import json
import re
from core import ControlError


def timer_payload(item, form, timer=None):
    time = form.get("time", "")
    loops = form.get("loops", "")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
        raise ControlError("Heure de programmation invalide.")
    if loops != "0" and not re.fullmatch(r"[01]{7}", loops):
        raise ControlError("Jours de répétition invalides.")
    if type(form.get("power")) is not bool or type(form.get("enabled")) is not bool or type(form.get("notify")) is not bool:
        raise ControlError("Réglages de programmation invalides.")
    alias = form.get("alias", "")
    if not isinstance(alias, str) or len(alias) > 100:
        raise ControlError("La remarque doit contenir au maximum 100 caractères.")
    previous_dps = (timer or {}).get("dps", {})
    if isinstance(previous_dps, str):
        try:
            previous_dps = json.loads(previous_dps)
        except ValueError:
            raise ControlError("Réglages de l'horaire existant non reconnus.") from None
    if not isinstance(previous_dps, dict):
        raise ControlError("Réglages de l'horaire existant non reconnus.")
    dps = dict(previous_dps)
    switch = item["lsc_functions"]["switch_led"]["id"]
    dps[switch] = form["power"]
    # Retain extra action fields when editing, e.g. date, timezone and params.
    action = {k:timer[k] for k in ("date", "timezoneId", "params") if timer and k in timer}
    action.setdefault("timezoneId", item.get("lsc_timezone", "Europe/Paris"))
    action.update(time=time, dps=dps)
    payload = {"bizId":item["device_id"], "bizType":0,
        "loops":loops, "status":int(form["enabled"]),
        "actions":json.dumps(action,separators=(",", ":")),
        "isAppPush":form["notify"],"aliasName":alias}
    if timer:
        timer_id = timer.get("timerId")
        if type(timer_id) not in (int, str) or not str(timer_id).isdigit():
            raise ControlError("Identifiant de programmation invalide.")
        payload["id"] = int(timer_id)
    else:
        payload["category"] = "switch_led"
    return payload


def save_timer(account, item, form, timer=None):
    payload = timer_payload(item,form,timer)
    api = "thing.m.clock.dps.update" if timer else "thing.m.clock.dps.add"
    result = account.request(api,payload,gid=item["lsc_home_id"],timezone_id=(timer or {}).get("timezoneId",item.get("lsc_timezone","Europe/Paris")))
    if result is False or result is None:
        raise ControlError("LSC n'a pas confirmé l'enregistrement de cet horaire.")
    return result


def set_timer_status(account, item, timer_id, status):
    if type(status) is not int or status not in (0,1,2) or not str(timer_id).isdigit():
        raise ControlError("Modification de programmation invalide.")
    result = account.request("thing.m.clock.batch.status.update",{
        "bizId":item["device_id"],"bizType":0,"ids":str(timer_id),"status":status},gid=item["lsc_home_id"])
    if result is not True:
        raise ControlError("LSC n'a pas confirmé la modification de cet horaire.")
    return result
