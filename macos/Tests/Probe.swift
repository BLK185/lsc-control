import Foundation
import WidgetKit

@main
struct ControlsProbe {
    @MainActor
    static func main() async throws {
        guard let code = ProcessInfo.processInfo.environment["LSC_TEST_CONTROLS_CODE"] else {
            fatalError("Missing synthetic test capability")
        }
        UserDefaults.standard.removeObject(forKey: ControlsClient.preference)
        let emptyConfiguration = LightConfiguration()
        let emptyValue = try await LampProvider().currentValue(configuration: emptyConfiguration)
        guard emptyValue.id == "unconfigured" else { fatalError("Empty control must have a usable placeholder") }
        let emptyLights = try await LightQuery().suggestedEntities()
        guard emptyLights.isEmpty else { fatalError("Unpaired editor must be able to open without network") }
        let lights = try await ControlsClient.lights(code: code)
        guard lights.map(\.id) == ["all", "a65", "a60"] else {
            fatalError("Dynamic lighting inventory not returned")
        }
        var first = LightConfiguration()
        first.code = code
        first.light = LSCLight(id: "a65", name: "First lamp")
        var second = LightConfiguration()
        second.code = code
        second.light = LSCLight(id: "a60", name: "Second lamp")
        let firstValue = try await LampProvider().currentValue(configuration: first)
        let secondValue = try await LampProvider().currentValue(configuration: second)
        guard firstValue.id != secondValue.id else { fatalError("Separate controls must keep distinct lamps") }
        var action = SetLampPower(identifier: secondValue.id, code: secondValue.code)
        action.value = true
        let _ = try await action.perform()
        guard try await ControlsClient.power("a60") else { fatalError("Native intent did not command selected lamp") }
        try await ControlsClient.setPower("a60", value: true)
        guard try await ControlsClient.power("a60") else { fatalError("Power readback failed") }
        try await ControlsClient.setPower("all", value: false)
        let allOn = try await ControlsClient.power("all")
        guard !allOn else { fatalError("Group command failed") }
        do {
            let _ = try await ControlsClient.lights(code: String(repeating: "x", count: 43))
            fatalError("Invalid capability was accepted")
        } catch is ControlsError { }
        print("Swift controls: empty editor, unconfigured placeholder, independent lamp configurations, native intent, readback and authentication verified.")
    }
}
