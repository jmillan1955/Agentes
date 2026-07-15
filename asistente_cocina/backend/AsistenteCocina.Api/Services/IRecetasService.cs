using AsistenteCocina.Api.Dtos;
using AsistenteCocina.Api.Models;

namespace AsistenteCocina.Api.Services;

public interface IRecetasService
{
    Task<List<string>> ObtenerCategoriasAsync();
    Task<List<Receta>> ObtenerRecetasPorCategoriaAsync(string categoria);
    Task<Receta?> ObtenerRecetaPorIdAsync(int id);
    Task<Receta> CrearRecetaAsync(CrearRecetaRequest request);
}