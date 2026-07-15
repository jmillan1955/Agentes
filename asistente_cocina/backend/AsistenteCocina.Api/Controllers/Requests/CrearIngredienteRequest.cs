// Requests/CrearIngredienteRequest.cs

namespace AsistenteCocina.Api;
public record CrearIngredienteRequest(
    double Cantidad,
    string Unidad,
    string NombreIngrediente
);