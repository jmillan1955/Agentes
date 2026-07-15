# -------------------------------
# SCRIPT CREACIÓN PROYECTO
# NET8 + Angular 20
# Nombre: Asistente-cocina
# -------------------------------

Write-Host "Creando proyecto Asistente-cocina .NET + Angular..."

# Crear carpeta raíz
mkdir Asistente-cocina
cd Asistente-cocina

# -------------------------------
# 1) CREAR BACKEND .NET 8
# -------------------------------
Write-Host "Creando backend .NET 8..."

dotnet new webapi -n AsistenteCocina.Api

# Habilitar CORS básico
$program = @"
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(p =>
        p.AllowAnyHeader()
         .AllowAnyMethod()
         .WithOrigins(""http://localhost:4200""));
});

var app = builder.Build();

app.UseCors();

app.MapGet("/api/categorias", () =>
{
    return new[] { "Arroces", "Bizcochos", "Pan", "Postres" };
});

app.MapGet("/api/recetas/{categoria}", (string categoria) =>
{
    return new[]
    {
        new { nombre = "Receta ejemplo 1" },
        new { nombre = "Receta ejemplo 2" }
    };
});

app.MapGet("/api/ingredientes/{receta}", (string receta) =>
{
    return new[]
    {
        new { porcentaje = "100%", nombre = "harina" },
        new { porcentaje = "70%", nombre = "agua" }
    };
});

app.Run();
"@

Set-Content -Path ".\AsistenteCocina.Api\Program.cs" -Value $program

# -------------------------------
# 2) CREAR FRONTEND ANGULAR
# -------------------------------cd a
Write-Host "Creando frontend Angular 20..."

npx -p @angular/cli ng new AsistenteCocina --routing --style=css

cd AsistenteCocina

# -------------------------------
# 3) GENERAR COMPONENTES ANGULAR
# -------------------------------
Write-Host "Generando componentes..."

# Pantalla principal
ng g c pages/categorias

# Lista de recetas
ng g c pages/recetas

# Editor de receta
ng g c pages/editar-receta

# Servicio API
ng g s services/cocina

# -------------------------------
# 4) GENERAR RUTAS
# -------------------------------

$routes = @"
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { CategoriasComponent } from './pages/categorias/categorias.component';
import { RecetasComponent } from './pages/recetas/recetas.component';
import { EditarRecetaComponent } from './pages/editar-receta/editar-receta.component';

const routes: Routes = [
  { path: '', component: CategoriasComponent },
  { path: 'recetas/:categoria', component: RecetasComponent },
  { path: 'editar/:receta', component: EditarRecetaComponent },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
"@

Set-Content -Path ".\src\app\app-routing.module.ts" -Value $routes

# -------------------------------
# 5) GENERAR SERVICIO API
# -------------------------------

$service = @"
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class CocinaService {

  api = 'http://localhost:5000/api';

  constructor(private http: HttpClient) {}

  getCategorias() {
    return this.http.get<string[]>(`${this.api}/categorias`);
  }

  getRecetas(categoria: string) {
    return this.http.get<any[]>(`${this.api}/recetas/${categoria}`);
  }

  getIngredientes(receta: string) {
    return this.http.get<any[]>(`${this.api}/ingredientes/${receta}`);
  }
}
"@

Set-Content -Path ".\src\app\services\cocina.service.ts" -Value $service

# -------------------------------
# 6) TERMINADO
# -------------------------------
Write-Host "`nProyecto Asistente-cocina creado!"
Write-Host "Backend: ./AsistenteCocina.Api"
Write-Host "Frontend: ./AsistenteCocina"
Write-Host "`nEjecutar:"
Write-Host " dotnet run --project AsistenteCocina.Api"
Write-Host " ng serve --open"
