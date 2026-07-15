import { Component } from '@angular/core';
import { Categorias } from './pages/categorias/categorias';

@Component({
  selector: 'app-root',
  imports: [Categorias],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {}