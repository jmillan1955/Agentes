import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsistenteCocinaService } from '../../services/asistente-cocina';
import { Receta } from '../receta/receta';
import { Cocinar } from '../cocinar/cocinar';

@Component({
  selector: 'app-categorias',
  standalone: true,
  imports: [FormsModule, Receta, Cocinar],
  templateUrl: './categorias.html',
  styleUrl: './categorias.scss'
})
export class Categorias implements OnInit {



  categorias: string[] = [];
  recetasPorCategoria: Record<string, any[]> = {};
  categoriasAbiertas: Record<string, boolean> = {};

  recetaEditando: any = null;
  recetaCocinando: any = null;

  textoBusqueda = '';

  mostrarFormularioNuevaReceta = false;
  nuevaRecetaNombre = '';
  nuevaRecetaCategoria = '';
  nuevaCategoriaManual = '';
  nuevaRecetaPesoRacion: number | null = 100;

  recetaFormularioEditando: any = null;
  editarNombre = '';
  editarPesoRacion: number | null = 100;

  cargando = true;
  error = '';

  constructor(private asistenteCocinaService: AsistenteCocinaService) {}

  ngOnInit(): void {
    this.cargarDatos();
  }

  cargarDatos(): void {
    this.cargando = true;
    this.error = '';
    this.recetasPorCategoria = {};
    this.categoriasAbiertas = {};

    this.asistenteCocinaService.obtenerCategorias().subscribe({
      next: (categorias: string[]) => {
        this.categorias = ['TODAS', ...categorias];
        this.categoriasAbiertas['TODAS'] = true;

        this.cargarRecetasCategorias(categorias);
      },
      error: () => {
        this.error = 'No se pudieron cargar las categorías';
        this.cargando = false;
      }
    });
  }

  get recetasOrdenadasAZ(): any[] {
    return Object.values(this.recetasPorCategoria)
      .flat()
      .sort((a: any, b: any) =>
        a.nombre.localeCompare(b.nombre, 'es', {
          sensitivity: 'base'
        })
      );
  }



  private cargarRecetasCategorias(categorias: string[]): void {
    let pendientes = categorias.length;

    if (pendientes === 0) {
      this.cargando = false;
      return;
    }

    categorias.forEach(categoria => {
    this.asistenteCocinaService.obtenerRecetasPorCategoria(categoria).subscribe({
      next: respuesta => {
        this.recetasPorCategoria[categoria] = respuesta;
        pendientes--;

        if (pendientes === 0) {
          this.cargando = false;
        }
      },
      error: () => {
        this.recetasPorCategoria[categoria] = [];
        pendientes--;

        if (pendientes === 0) {
          this.cargando = false;
        }
      }
      });
    });
  }

  toggleCategoria(categoria: string): void {
    this.categoriasAbiertas[categoria] = !this.categoriasAbiertas[categoria];
  }

  abrirReceta(receta: any): void {
    this.recetaEditando = receta;
  }

  abrirCocinar(receta: any): void {
    this.recetaCocinando = receta;
  }

  volverDesdeReceta(): void {
    this.recetaEditando = null;
    this.cargarDatos();
  }

  volverDesdeCocinar(): void {
    this.recetaCocinando = null;
  }

  limpiarBusqueda(): void {
    this.textoBusqueda = '';
  }

  get hayBusqueda(): boolean {
    return this.textoBusqueda.trim().length > 0;
  }

  get recetasFiltradas(): any[] {
    const texto = this.textoBusqueda.trim().toLowerCase();

    if (!texto) {
      return [];
    }

    return Object.values(this.recetasPorCategoria)
      .flat()
      .filter(receta =>
        receta.nombre.toLowerCase().includes(texto) ||
        receta.categoria?.toLowerCase().includes(texto)
      );
  }

  recetasCategoria(categoria: string): any[] {
    if (categoria === 'TODAS') {
      return this.recetasOrdenadasAZ;
    }



    return this.recetasPorCategoria[categoria] ?? [];
  }

  toggleNuevaReceta(): void {
    this.mostrarFormularioNuevaReceta = !this.mostrarFormularioNuevaReceta;

    if (this.mostrarFormularioNuevaReceta) {
      this.nuevaRecetaNombre = '';
      this.nuevaRecetaCategoria = '';
      this.nuevaCategoriaManual = '';
      this.nuevaRecetaPesoRacion = 100;
    }
  }

  guardarReceta(): void {
    const nombre = this.nuevaRecetaNombre.trim();

    const categoria =
      this.nuevaCategoriaManual.trim() ||
      this.nuevaRecetaCategoria.trim();

    const pesoRacion = this.nuevaRecetaPesoRacion ?? 0;

    if (!nombre || !categoria || pesoRacion <= 0) {
      alert('Debes indicar nombre, categoría y peso de ración');
      return;
    }

    this.asistenteCocinaService.crearReceta({
      nombre,
      categoria,
      pesoRacion
    }).subscribe({
      next: recetaCreada => {
        this.mostrarFormularioNuevaReceta = false;

        this.nuevaRecetaNombre = '';
        this.nuevaRecetaCategoria = '';
        this.nuevaCategoriaManual = '';
        this.nuevaRecetaPesoRacion = 100;

        this.cargarDatos();
        this.recetaEditando = recetaCreada;
      },
      error: () => {
        this.error = 'No se pudo crear la receta';
      }
    });
  }

  editarReceta(receta: any): void {
  this.recetaFormularioEditando = receta;
  this.editarNombre = receta.nombre;
  this.editarPesoRacion = receta.pesoRacion ?? 100;
  }

  cancelarEdicionReceta(): void {
    this.recetaFormularioEditando = null;
    this.editarNombre = '';
    this.editarPesoRacion = 100;
  }

  guardarEdicionReceta(): void {
    if (!this.recetaFormularioEditando) {
      return;
    }

    const nombre = this.editarNombre.trim();
    const pesoRacion = this.editarPesoRacion ?? 0;

    if (!nombre || pesoRacion <= 0) {
      alert('Debes indicar nombre y peso de ración');
      return;
    }

    this.asistenteCocinaService.actualizarReceta(
      this.recetaFormularioEditando.id,
      {
        nombre,
        pesoRacion
      }
    ).subscribe({
      next: () => {
        this.cancelarEdicionReceta();
        this.cargarDatos();
      },
      error: () => {
        this.error = 'No se pudo actualizar la receta';
      }
    });
  }

  borrarReceta(receta: any): void {
    if (!confirm(`¿Borrar la receta "${receta.nombre}"?`)) {
      return;
    }

    this.asistenteCocinaService.eliminarReceta(receta.id).subscribe({
      next: () => {
        this.cargarDatos();
      },
      error: () => {
        this.error = 'No se pudo borrar la receta';
      }
    });
  }
}