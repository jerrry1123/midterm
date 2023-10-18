class Pool:
    def __init__(self, intra_rate, inter_rate, death_rate, population, initial_infection_rate):
        self.intra_rate = intra_rate
        self.inter_rate = inter_rate
        self.death_rate = death_rate
        self.uninfected = population * (1 - initial_infection_rate)
        self.infected = population * initial_infection_rate
        self.dead = 0

    def get_population(self):
        # gets the total population of the pool
        if (self.infected + self.uninfected == 0):
            return 1
        return self.uninfected + self.infected


class Pool_Group:
    def __init__(self, pools, min_age, contact_rate):
        self.vaccinated = pools[0]
        self.unvaccinated = pools[1]
        self.min_age = min_age
        self.contact_rate = contact_rate

    def get_population(self):
        # gets the total population of the two pools in the group, represents the
        # total population of the age group
        return self.vaccinated.get_population() + self.unvaccinated.get_population()


class Simulation:
    def __init__(self, pools, infection_rate, vax_order, vax_rate, recovery_rate):
        # pools should be a Pool_Group object
        # infection_rate is the baseline rate at which people get infected
        # vaccination order is an array of the order in which pools get vaccines
        # base_rate should be the number of contacts(no matter the status) times
        # the probability of infection
        self.pools = pools
        self.base_rate = infection_rate
        self.recovery_rate = recovery_rate
        self.vaccination_order = vax_order
        self.vaccination_rate = vax_rate
        self.population = self.get_total_population()

    def get_total_population(self):
        # gets the total population of the simulation, which can change with deaths
        # and can be initialized differently
        ans = 0
        for group in self.pools.values():
            ans += group.vaccinated.uninfected + group.unvaccinated.uninfected
        return ans + self.get_total_infections()

    def get_total_infections(self):
        # gets the total number of people infected
        ans = 0
        for group in self.pools.values():
            ans += group.vaccinated.infected + group.unvaccinated.infected
        return ans

    def get_total_deaths(self):
        # gets the total number of deaths
        ans = 0
        for group in self.pools.values():
            ans += group.vaccinated.dead + group.unvaccinated.dead
        return ans

    def vaccinate(self):
        # step through one day of vaccination according to the policy
        # only vaccinate uninfected people, assume the infected will recover to a vaccinated status
        vax_left = self.vaccination_rate
        for group in self.vaccination_order:  # vaccinates in order
            pool = self.pools.get(group)

            # gets the amount of vaccines for this group
            vax_amount = min(vax_left, pool.unvaccinated.uninfected)
            vax_left -= vax_amount

            # transfer the vaccinated to the new pool
            pool.unvaccinated.uninfected -= vax_amount
            pool.vaccinated.uninfected += vax_amount
            if vax_left == 0:
                break

    def infect_and_kill(self, min_age, vaccinated, original_pools, total_infected):
        # processes the infections and deaths for one pool based on the data from
        # the last time step so that no recursion happens
        pool_group = original_pools.get(min_age)
        if vaccinated:
            pool = pool_group.vaccinated
        else:
            pool = pool_group.unvaccinated

        # calculate deaths as a percentage of the infected
        deaths = pool.infected * pool.death_rate

        # add up the number of infected from within the same pool, same pool group,
        # and all other pools
        infections = 0
        percentage = pool.uninfected / pool.get_population()
        # assume that the contact rate is the same for all infected people

        # calculate intra-pool infections
        infections += self.base_rate * pool.intra_rate * \
            percentage * pool.infected * pool.get_population() / self.population
        # print("Intra: ", infections)

        # calculate infections from the other pool inside the group
        if vaccinated:
            cross_population = pool_group.unvaccinated.infected
        else:
            cross_population = pool_group.vaccinated.infected
        infections += self.base_rate * pool_group.contact_rate * \
            percentage * cross_population * pool.get_population() / self.population
        # print("Cross: ", infections)

        # calculate infections from the rest of the population
        infections += self.base_rate * pool.inter_rate * percentage * \
            (total_infected - pool.infected - cross_population) * \
            pool.get_population() / self.population
        # print("Inter: ", infections)

        # update values
        if vaccinated:
            actual_pool = self.pools.get(min_age).vaccinated
        else:
            actual_pool = self.pools.get(min_age).unvaccinated
        actual_pool.uninfected -= infections
        actual_pool.infected += infections - deaths
        actual_pool.dead += deaths

    def recover(self, min_age):
        # processes the recoveries for a pool group, moving the infected
        # to the vaccinated to account for immunity after transmission
        group = self.pools.get(min_age)

        # calculate and process unvaccinated recoveries
        unvaccinated_recoveries = group.unvaccinated.infected * self.recovery_rate
        group.unvaccinated.infected -= unvaccinated_recoveries
        group.vaccinated.uninfected = unvaccinated_recoveries

        # calculate and process vaccinated recoveries
        vaccinated_recoveries = group.vaccinated.infected * self.recovery_rate
        group.vaccinated.infected -= vaccinated_recoveries
        group.vaccinated.uninfected += vaccinated_recoveries

    def step(self):
        # goes through one time step of the simulation, first vaccinating,
        # then calculating new infections from pools, and finally
        # calculating any recoveries
        self.vaccinate()
        original_pools = self.pools
        total_infected = self.get_total_infections()
        for age in self.vaccination_order:
            self.infect_and_kill(age, True, original_pools, total_infected)
            self.infect_and_kill(age, False, original_pools, total_infected)
            self.recover(age)


# how much the vaccine helps at stopping transmission and death
VACCINATION_EFFICIENCY = 0.1
# change in base contact rate among vaccinated pools to account for the
# fact that they know they are immune
VACCINATED_HANGOUT_RATE = 1.5
# change in base contact rate among unvaccinated pools to account for the fact
# that they want to keep themselves safe
UNVACCINATED_HANGOUT_RATE = 0.8
# base percentage chance of an infected person dying of Covid per day
MORTALITY_RATE = 0.001
# starting percentage of each pool that is infected
INITIAL_INFECTION_RATE = 0.001
# Base contact rate for the two pools within the pool group
CONTACT_RATE = 0.5
# Amount of expected infections per infected person per day
BASE_RATE = 2.28/14 * 2
# Amount of vaccines available per day
VAX_RATE = 3500/30


# 0-9
# children have extra contact among themselves, so their intra_rate and
# contact_rate are higher but are less likely to die of covid
pools_0 = [Pool(
    intra_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE * 2,
    inter_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE,
    death_rate=VACCINATION_EFFICIENCY * MORTALITY_RATE,
    population=0,
    initial_infection_rate=INITIAL_INFECTION_RATE), Pool(
    intra_rate=UNVACCINATED_HANGOUT_RATE * 2,
    inter_rate=UNVACCINATED_HANGOUT_RATE,
    death_rate=MORTALITY_RATE/10,
    population=6000,
    initial_infection_rate=INITIAL_INFECTION_RATE)]
Group_0 = Pool_Group(pools=pools_0, min_age=0, contact_rate=CONTACT_RATE * 2)

# 10-19
# children have extra contact among themselves, so their intra_rate and
# contact_rate are higher but are less likely to die of covid
pools_10 = [Pool(
    intra_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE * 2,
    inter_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE,
    death_rate=VACCINATION_EFFICIENCY * MORTALITY_RATE,
    population=0,
    initial_infection_rate=INITIAL_INFECTION_RATE), Pool(
    intra_rate=UNVACCINATED_HANGOUT_RATE * 2,
    inter_rate=UNVACCINATED_HANGOUT_RATE,
    death_rate=MORTALITY_RATE/10,
    population=18000,
    initial_infection_rate=INITIAL_INFECTION_RATE)]
Group_10 = Pool_Group(pools=pools_10, min_age=10,
                      contact_rate=CONTACT_RATE * 2)

# ADULTS (20-60)
# Use all standard constants
pools_20 = [Pool(
    intra_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE,
    inter_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE,
    death_rate=VACCINATION_EFFICIENCY * MORTALITY_RATE,
    population=0,
    initial_infection_rate=INITIAL_INFECTION_RATE), Pool(
    intra_rate=UNVACCINATED_HANGOUT_RATE,
    inter_rate=UNVACCINATED_HANGOUT_RATE,
    death_rate=MORTALITY_RATE,
    population=65000,
    initial_infection_rate=INITIAL_INFECTION_RATE)]
Group_20 = Pool_Group(pools=pools_20, min_age=20, contact_rate=CONTACT_RATE)

# 70+
# The elderly are more likely to die of covid
pools_70 = [Pool(
    intra_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE,
    inter_rate=VACCINATION_EFFICIENCY * VACCINATED_HANGOUT_RATE,
    death_rate=VACCINATION_EFFICIENCY * MORTALITY_RATE * 10,
    population=0,
    initial_infection_rate=INITIAL_INFECTION_RATE), Pool(
    intra_rate=UNVACCINATED_HANGOUT_RATE,
    inter_rate=UNVACCINATED_HANGOUT_RATE,
    death_rate=MORTALITY_RATE * 10,
    population=11000,
    initial_infection_rate=INITIAL_INFECTION_RATE)]
Group_70 = Pool_Group(pools=pools_70, min_age=70, contact_rate=CONTACT_RATE)
pools = {0: Group_0, 10: Group_10, 20: Group_20, 70: Group_70}

# Order of vaccination
policy = [70, 0, 10, 20]

# Run simulation
simulation = Simulation(pools=pools, infection_rate=BASE_RATE, vax_order=policy,
                        vax_rate=VAX_RATE, recovery_rate=0.07)
for i in range(100):
    simulation.step()
    print("Day: ", i)
    print("Infected: ", simulation.get_total_infections())
    print("Dead: ", simulation.get_total_deaths())

# 0, 10, 70, 20 => 4396 infected, 102 dead
# 0, 70, 10, 20 => 4461 infected, 84 dead
# 70, 0, 10, 20 => 4528 infected, 74 dead
