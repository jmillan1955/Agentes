import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnDestroy, Output } from '@angular/core';

interface PasoCronograma {
  numpaso: number;
  mensaje: string;
  cronometro: boolean;
  tiempo?: string;
}

interface RecetaCronograma {
  idreceta: number;
  nombre: string;
  ingredientes: string[];
  pasos: PasoCronograma[];
}

@Component({
  selector: 'app-cronograma',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './cronograma.html',
  styleUrls: ['./cronograma.scss']
})
export class Cronograma implements OnDestroy {

  @Input() recetaBase: any = null;
  @Output() cerrar = new EventEmitter<void>();

  receta: RecetaCronograma = {
    idreceta: 23,
    nombre: 'Manzanas asadas',
    ingredientes: [
      '4 manzanas golden',
      'Un poco de azúcar',
      'Agua o vino blanco'
    ],
    pasos: [
      {
        numpaso: 1,
        mensaje: 'Preparar y mostrar ingredientes',
        cronometro: false
      },
      {
        numpaso: 2,
        mensaje:
          'Lavar las manzanas, quitarles el corazón y poner en el hueco un poco de azúcar y un poco de agua o vino. Poner en la airfryer 10 minutos a 180º.',
        cronometro: true,
        tiempo: '00:01:00'
      },
      {
        numpaso: 3,
        mensaje:
          'Dar la vuelta a las manzanas y cocinar otros 10 minutos.',
        cronometro: true,
        tiempo: '00:01:00'
      }
    ]
  };  

  indicePasoActual = 0;

  cronometroActivo = false;
  segundosRestantes = 0;
  intervalo: any;

  get pasoActual(): PasoCronograma {
    return this.receta.pasos[this.indicePasoActual];
  }

  siguiente(): void {

    if (this.indicePasoActual < this.receta.pasos.length - 1) {
      this.pararCronometro();
      this.indicePasoActual++;
    }
  }

  anterior(): void {

    if (this.indicePasoActual > 0) {
      this.pararCronometro();
      this.indicePasoActual--;
    }
  }

  iniciarCronometro(): void {

    if (!this.pasoActual.tiempo) {
      return;
    }

    this.segundosRestantes = this.convertirTiempoASegundos(this.pasoActual.tiempo);

    this.cronometroActivo = true;

    this.intervalo = setInterval(() => {

      this.segundosRestantes--;

      if (this.segundosRestantes <= 0) {
        this.finalizarCronometro();
      }

    }, 1000);
  }

  pararCronometro(): void {

    clearInterval(this.intervalo);
    this.cronometroActivo = false;
  }

  finalizarCronometro(): void {

    this.pararCronometro();

    this.reproducirAlarma();

    alert('Tiempo finalizado');
  }

  convertirTiempoASegundos(tiempo: string): number {

    const partes = tiempo.split(':').map(Number);

    const horas = partes[0];
    const minutos = partes[1];
    const segundos = partes[2];

    return (horas * 3600) + (minutos * 60) + segundos;
  }

  formatearTiempo(segundos: number): string {

    const horas = Math.floor(segundos / 3600)
      .toString()
      .padStart(2, '0');

    const minutos = Math.floor((segundos % 3600) / 60)
      .toString()
      .padStart(2, '0');

    const segs = Math.floor(segundos % 60)
      .toString()
      .padStart(2, '0');

    return `${horas}:${minutos}:${segs}`;
  }

  reproducirAlarma(): void {

    const audio = new Audio('assets/alarma.mp3');
    audio.play();
  }
  cerrarCronograma(): void {
    this.pararCronometro();
    this.indicePasoActual = 0;
    this.cerrar.emit();
  }

  ngOnDestroy(): void {

    clearInterval(this.intervalo);
  }
}