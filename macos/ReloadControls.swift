import Foundation
import WidgetKit

@_cdecl("lsc_reload_controls")
public func reloadControls() {
    ControlCenter.shared.reloadControls(ofKind: "fr.carfr.LSCControl.Power")
}
