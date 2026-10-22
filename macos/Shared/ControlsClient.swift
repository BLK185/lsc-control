import Foundation

enum ControlsError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        switch self { case .message(let text): return text }
    }
}

struct LightRecord: Codable, Hashable, Sendable {
    let id: String
    let name: String
}

struct LightsReply: Decodable { let lights: [LightRecord] }
struct PowerReply: Decodable { let power: Bool }

final class LoopbackSession: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

enum ControlsClient {
    static let root = "http://127.0.0.1:47832"
    static let preference = "localControlsCapability"

    static func validCode(_ code: String) -> Bool {
        code.range(of: "^[A-Za-z0-9_-]{32,64}$", options: .regularExpression) != nil
    }

    static func code(_ provided: String? = nil) throws -> String {
        let value = provided?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let token = value.isEmpty ? UserDefaults.standard.string(forKey: preference) ?? "" : value
        guard validCode(token) else {
            throw ControlsError.message("Dans LSC Control, ouvre Centre de contrôle… puis copie le code de connexion.")
        }
        return token
    }

    static func request<T: Decodable>(_ path: String, code provided: String? = nil,
                                      body: Data? = nil) async throws -> T {
        let token = try code(provided)
        guard path == "/lights" || path == "/power" || path.hasPrefix("/power/") else {
            throw ControlsError.message("Commande inconnue.")
        }
        var request = URLRequest(url: URL(string: root + path)!)
        request.timeoutInterval = body == nil ? 5 : 20
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        if let body {
            request.httpMethod = "POST"
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil
        configuration.urlCache = nil
        let session = URLSession(configuration: configuration, delegate: LoopbackSession(), delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse, data.count <= 262144 else {
                throw ControlsError.message("Réponse LSC invalide.")
            }
            guard http.statusCode == 200 else {
                if http.statusCode == 401 {
                    throw ControlsError.message("Le code a changé. Recopie-le depuis LSC Control → Centre de contrôle…")
                }
                throw ControlsError.message("Éclairage indisponible. Vérifie son état dans LSC Control.")
            }
            let result = try JSONDecoder().decode(T.self, from: data)
            // Store only the local power-control capability, after validation.
            // The extension has its own sandbox; no App Group or LSC credential
            // is shared with it. Other controls can reuse this pairing.
            if UserDefaults.standard.string(forKey: preference) != token {
                UserDefaults.standard.set(token, forKey: preference)
            }
            return result
        } catch let error as ControlsError { throw error }
        catch {
            throw ControlsError.message("Ouvre LSC Control sur ce Mac et laisse l’app active dans la barre des menus.")
        }
    }

    static func lights(code: String? = nil) async throws -> [LightRecord] {
        let reply: LightsReply = try await request("/lights", code: code)
        return [LightRecord(id: "all", name: "Tous les éclairages")] + reply.lights
    }

    static func power(_ id: String, code: String? = nil) async throws -> Bool {
        guard id.range(of: "^[A-Za-z0-9_-]{1,100}$", options: .regularExpression) != nil else {
            throw ControlsError.message("Éclairage inconnu.")
        }
        let reply: PowerReply = try await request("/power/" + id, code: code)
        return reply.power
    }

    static func setPower(_ id: String, value: Bool, code: String? = nil) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["id": id, "value": value])
        let _: PowerReply = try await request("/power", code: code, body: body)
    }
}
