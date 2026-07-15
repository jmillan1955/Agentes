// Requests/CrearRecetaRequest.cs

namespace AsistenteCocina.Api;

public record CrearRecetaRequest(
    string Nombre,
    string Categoria,
    double PesoRacion
);