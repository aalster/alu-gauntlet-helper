from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars import Car
from alu_gauntlet_helper.services.tracks import TrackView


def init_data():
    for car in cars:
        APP_CONTEXT.cars_service.save(car)
    for track in tracks:
        APP_CONTEXT.tracks_service.save(track)


# https://asphalt9.info/asphalt9/tuning/asphalt-9-car-list/
# console.log([...document.querySelectorAll('#tablepress-3 a')]
#   .map(a => 'Car(name="' + a.text + '")')
#   .reduce((a, b) => a + ",\n" + b))
cars = [
    Car(name="Lamborghini Centenario"),
    Car(name="Ferrari FXX-K"),
    Car(name="Lamborghini Autentica"),
    Car(name="Icona Vulcano Titanium"),
    Car(name="W Motors Lykan HyperSport"),
    Car(name="Raesr Tachyon Speed"),
    Car(name="Jaguar XJ220S TWR"),
    Car(name="Lamborghini Veneno"),
    Car(name="ATS Automobili GT"),
    Car(name="Lamborghini Egoista"),
    Car(name="Chrysler ME412"),
    Car(name="TRION Nemesis"),
    Car(name="Spania GTA 2015 GTA Spano"),
    Car(name="Nissan GT-R Neon Edition"),
    Car(name="Ferrari SF90 Stradale"),
    Car(name="FV Frangivento Sorpasso GT3"),
    Car(name="Bugatti Veyron 16.4 Grand Sport Vitesse"),
    Car(name="McLaren Senna"),
    Car(name="Lamborghini Terzo Millennio"),
    Car(name="Vision 1789"),
    Car(name="W Motors Fenyr Supersport"),
    Car(name="Aston Martin Valkyrie"),
    Car(name="Zenvo TS1 GT Anniversary"),
    Car(name="Rimac Concept S"),
    Car(name="Automobili Pininfarina Battista"),
    Car(name="Naran Hyper Coupe"),
    Car(name="McLaren Speedtail"),
    Car(name="Faraday FFZERO1"),
    Car(name="Koenigsegg Regera"),
    Car(name="Saleen S7 Twin Turbo"),
    Car(name="Ultima RS"),
    Car(name="Lamborghini Sian FKP 37"),
    Car(name="Ajlani Drakuma"),
    Car(name="Inferno Automobili Inferno"),
    Car(name="Torino Design Super Sport"),
    Car(name="Bugatti Chiron"),
    Car(name="BXR Bailey Blade GT1"),
    Car(name="Bugatti Divo"),
    Car(name="Tushek TS 900 Racer Pro"),
    Car(name="Mazzanti Evantra Millecavalli"),
    Car(name="Toroidion 1MW"),
    Car(name="Inferno Settimo Cerchio"),
    Car(name="Bugatti Chiron Pur Sport"),
    Car(name="Koenigsegg Jesko"),
    Car(name="Bugatti Centodieci"),
    Car(name="W Motors Lykan Neon"),
    Car(name="Bugatti Mistral"),
    Car(name="Aspark Owl"),
    Car(name="Rimac Nevera"),
    Car(name="Koenigsegg Agera RS"),
    Car(name="SSC Tuatara"),
    Car(name="Bugatti Chiron Super Sport 300+"),
    Car(name="Koenigsegg CCXR"),
    Car(name="Bugatti La Voiture Noire"),
    Car(name="Czinger 21C"),
    Car(name="Deus Vayanne"),
    Car(name="Koenigsegg Gemera"),
    Car(name="Zenvo Aurora Tur"),
    Car(name="Hennessey Venom F5"),
    Car(name="Koenigsegg CC850"),
    Car(name="Bugatti Bolide"),
    Car(name="Koenigsegg Jesko Absolut"),
    Car(name="Devel Sixteen"),
]

# https://asphalt9.info/asphalt9/game-mode/tracks/
# console.log([...document.querySelectorAll('#tablepress-11 tbody tr')]
#     .map(tr => 'TrackView(map_name="' + tr.querySelector('.column-2').textContent + '", name="' + (tr.querySelector('.column-3 a')?.text || tr.querySelector('.column-3').textContent) + '")')
#     .reduce((a, b) => a + ",\n" + b))
tracks = [
    TrackView(map_name="Auckland", name="Straight Sprint"),
    TrackView(map_name="Buenos Aires", name="La Boca"),
    TrackView(map_name="Buenos Aires", name="Water Run"),
    TrackView(map_name="Cairo", name="A Kings Revival"),
    TrackView(map_name="Cairo", name="Gezira Island"),
    TrackView(map_name="Himalayas", name="Freefall"),
    TrackView(map_name="Himalayas", name="Leap of Faith"),
    TrackView(map_name="Nevada", name="Bridge to Bridge"),
    TrackView(map_name="New York", name="A Run in the Park"),
    TrackView(map_name="New York", name="Friendly Neighborhood"),
    TrackView(map_name="New York", name="Wall Street Ride"),
    TrackView(map_name="Norway", name="Rocketing to the Future"),
    TrackView(map_name="Osaka", name="Meiji Rush"),
    TrackView(map_name="Osaka", name="Namba Park"),
    TrackView(map_name="Paris", name="Metro"),
    TrackView(map_name="Paris", name="Notre Dame"),
    TrackView(map_name="Rome", name="Roman Byroads"),
    TrackView(map_name="Rome", name="Roman Tumble"),
    TrackView(map_name="San Francisco", name="Railroad Bustle"),
    TrackView(map_name="San Francisco", name="The Tunnel"),
    TrackView(map_name="Scotland", name="Ghost Ships"),
    TrackView(map_name="Scotland", name="Rocky Valley"),
    TrackView(map_name="Shanghai", name="Double Roundabout"),
    TrackView(map_name="Shanghai", name="Paris of the East"),
    TrackView(map_name="Singapore", name="Urban Rush"),
    TrackView(map_name="The Caribbean", name="Hell Vale"),
    TrackView(map_name="The Caribbean", name="Islet Race"),
    TrackView(map_name="The Caribbean", name="Resort Dash"),
    TrackView(map_name="Tuscany", name="Riverine Launch"),
    TrackView(map_name="Tuscany", name="Versatile Trail"),
    TrackView(map_name="US Midwest", name="Its a Twister"),
    TrackView(map_name="US Midwest", name="Trainspotter")
]