import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router'; 
import { PropertySearchComponent } from './components/property-search/property-search';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, PropertySearchComponent],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {

}
