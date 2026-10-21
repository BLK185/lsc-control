import AppIntents
import SwiftUI
import WidgetKit

struct LSCLight: AppEntity {
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Éclairage LSC"
    static var defaultQuery = LightQuery()
    let id: String
    let name: String
    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: "\(name)") }
}

struct LightQuery: EntityQuery {
    @IntentParameterDependency<LightConfiguration>(\.$code)
    var configuration

    func suggestedEntities() async throws -> [LSCLight] {
        try await ControlsClient.lights(code: configuration?.code).map { LSCLight(id: $0.id, name: $0.name) }
    }

    func entities(for identifiers: [String]) async throws -> [LSCLight] {
        try await suggestedEntities().filter { identifiers.contains($0.id) }
    }
}

struct LightConfiguration: ControlConfigurationIntent {
    static var title: LocalizedStringResource = "Choisir un éclairage LSC"

    @Parameter(title: "Code de connexion (première utilisation)")
    var code: String?

    @Parameter(title: "Éclairage")
    var light: LSCLight?

    static var parameterSummary: some ParameterSummary {
        Summary("Commander \(\.$light)") { \.$code }
    }
}

struct LampValue: Sendable {
    let id: String
    let name: String
    let power: Bool
    let code: String?
}

struct LampProvider: AppIntentControlValueProvider {
    func previewValue(configuration: LightConfiguration) -> LampValue {
        LampValue(id: configuration.light?.id ?? "all", name: configuration.light?.name ?? "Éclairage LSC",
                  power: false, code: configuration.code)
    }

    func currentValue(configuration: LightConfiguration) async throws -> LampValue {
        guard let light = configuration.light else {
            throw ControlsError.message("Modifie cette commande pour choisir un éclairage.")
        }
        let records = try await ControlsClient.lights(code: configuration.code)
        guard let current = records.first(where: { $0.id == light.id }) else {
            throw ControlsError.message("Cet éclairage n’est plus dans le compte. Modifie la commande.")
        }
        let power = try await ControlsClient.power(current.id, code: configuration.code)
        return LampValue(id: current.id, name: current.name, power: power, code: configuration.code)
    }
}

struct SetLampPower: SetValueIntent {
    static var title: LocalizedStringResource = "Commander un éclairage LSC"
    @Parameter(title: "Éclairage") var identifier: String
    @Parameter(title: "Code de connexion") var code: String?
    @Parameter(title: "Allumé") var value: Bool

    init() { identifier = "all" }
    init(identifier: String, code: String?) { self.identifier = identifier; self.code = code }

    func perform() async throws -> some IntentResult {
        try await ControlsClient.setPower(identifier, value: value, code: code)
        ControlCenter.shared.reloadControls(ofKind: "fr.carfr.LSCControl.Power")
        return .result()
    }
}

struct LampControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        AppIntentControlConfiguration(kind: "fr.carfr.LSCControl.Power", provider: LampProvider()) { lamp in
            ControlWidgetToggle(LocalizedStringResource(stringLiteral: lamp.name), isOn: lamp.power,
                                action: SetLampPower(identifier: lamp.id, code: lamp.code)) { isOn in
                Label(isOn ? "Allumé" : "Éteint", systemImage: "lightbulb.fill")
            }
            .tint(Color(red: 138.0 / 255, green: 0, blue: 252.0 / 255))
        }
        .displayName("Éclairage LSC")
        .description("Allumer ou éteindre un éclairage du compte, ou tous ensemble. LSC Control doit rester ouvert.")
    }
}

@main
struct LSCControls: WidgetBundle {
    var body: some Widget { LampControl() }
}
