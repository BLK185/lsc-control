import Foundation

@main
struct ControlsProbe {
    static func main() async throws {
        guard let code = ProcessInfo.processInfo.environment["LSC_TEST_CONTROLS_CODE"] else {
            fatalError("Missing synthetic test capability")
        }
        let lights = try await ControlsClient.lights(code: code)
        guard lights.map(\.id) == ["all", "a65", "a60"] else {
            fatalError("Dynamic lighting inventory not returned")
        }
        try await ControlsClient.setPower("a60", value: true)
        guard try await ControlsClient.power("a60") else { fatalError("Power readback failed") }
        try await ControlsClient.setPower("all", value: false)
        guard try await !ControlsClient.power("all") else { fatalError("Group command failed") }
        do {
            let _ = try await ControlsClient.lights(code: String(repeating: "x", count: 43))
            fatalError("Invalid capability was accepted")
        } catch is ControlsError { }
        print("Swift client: inventory, individual/group power, readback and rejected capability verified.")
    }
}
