import Foundation
import WidgetKit

ControlCenter.shared.reloadControls(ofKind: "fr.carfr.LSCControl.Power")
RunLoop.current.run(until: Date().addingTimeInterval(0.2))
