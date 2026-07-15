// Requests/RenombrarRecetaRequest.cs

namespace AsistenteCocina.Api;

public record RenombrarRecetaRequest(
    string NuevoNombre,
    double PesoRacion
);